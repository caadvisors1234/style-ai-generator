"""
プロンプトプリセットAPI

プリセットプロンプトの一覧取得など。
"""

import logging
import json
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.conf import settings

from api.decorators import login_required_api
from images.models import PromptPreset
from images.services.prompt_improver import PromptImproverService, PromptImproverError


logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def prompts_list(request):
    """
    プロンプトプリセット一覧API

    GET /api/v1/prompts/

    Query Parameters:
        - category: string (optional) - カテゴリでフィルタ

    Response:
        {
            "status": "success",
            "prompts": [
                {
                    "id": int,
                    "name": "string",
                    "prompt": "string",
                    "category": "string",
                    "description": "string",
                    "display_order": int,
                    "is_favorite": bool (ログイン時のみ)
                }
            ]
        }
    """
    try:
        category = request.GET.get('category')

        # ログインユーザーの場合はキャッシュを使用しない（お気に入り状態を含むため）
        if request.user.is_authenticated:
            # データベースから取得
            prompts = PromptPreset.objects.filter(is_active=True)

            if category:
                prompts = prompts.filter(category=category)

            prompts = prompts.order_by('display_order', 'name')

            # お気に入りIDセットを取得
            from images.models import UserFavoritePrompt
            favorite_preset_ids = set(
                UserFavoritePrompt.objects.filter(
                    user=request.user
                ).values_list('preset_id', flat=True)
            )

            # レスポンスデータ構築（お気に入り状態を含む）
            prompts_data = [
                {
                    'id': prompt.id,
                    'name': prompt.name,
                    'prompt': prompt.prompt,
                    'category': prompt.category,
                    'description': prompt.description,
                    'display_order': prompt.display_order,
                    'is_favorite': prompt.id in favorite_preset_ids
                }
                for prompt in prompts
            ]

            response_data = {
                'status': 'success',
                'prompts': prompts_data
            }

            return JsonResponse(response_data)

        # 非ログイン時はキャッシュを使用
        cache_key = f"prompts_list:{category if category else 'all'}"

        # キャッシュから取得
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug(f"Prompts loaded from cache: {cache_key}")
            return JsonResponse(cached_data)

        # データベースから取得
        prompts = PromptPreset.objects.filter(is_active=True)

        if category:
            prompts = prompts.filter(category=category)

        prompts = prompts.order_by('display_order', 'name')

        # レスポンスデータ構築
        prompts_data = [
            {
                'id': prompt.id,
                'name': prompt.name,
                'prompt': prompt.prompt,
                'category': prompt.category,
                'description': prompt.description,
                'display_order': prompt.display_order
            }
            for prompt in prompts
        ]

        response_data = {
            'status': 'success',
            'prompts': prompts_data
        }

        # キャッシュに保存（1時間）
        cache.set(cache_key, response_data, 60 * 60)

        logger.info(f"Prompts loaded from database: count={len(prompts_data)}")

        return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"Prompts list error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'プリセット一覧の取得中にエラーが発生しました'
        }, status=500)


@require_http_methods(["GET"])
def prompts_categories(request):
    """
    プロンプトカテゴリ一覧API

    GET /api/v1/prompts/categories/

    Response:
        {
            "status": "success",
            "categories": [
                {
                    "value": "string",
                    "label": "string",
                    "count": int
                }
            ]
        }
    """
    try:
        # キャッシュキー
        cache_key = "prompts_categories"

        # キャッシュから取得
        cached_data = cache.get(cache_key)
        if cached_data:
            return JsonResponse(cached_data)

        # カテゴリ一覧（モデルのCHOICESから取得）
        categories_data = []

        for value, label in PromptPreset.CATEGORY_CHOICES:
            count = PromptPreset.objects.filter(
                category=value,
                is_active=True
            ).count()

            if count > 0:
                categories_data.append({
                    'value': value,
                    'label': label,
                    'count': count
                })

        response_data = {
            'status': 'success',
            'categories': categories_data
        }

        # キャッシュに保存（1時間）
        cache.set(cache_key, response_data, 60 * 60)

        return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"Prompts categories error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'カテゴリ一覧の取得中にエラーが発生しました'
        }, status=500)


@require_http_methods(["POST"])
@login_required_api
def improve_prompt(request):
    """
    プロンプト改善API（認証必須）

    POST /api/v1/prompts/improve/

    Request Body:
        {
            "prompt": "string (required)"
        }

    Response:
        {
            "status": "success",
            "original_prompt": "string",
            "improved_prompt": "string"
        }

    Error Response:
        {
            "status": "error",
            "message": "string",
            "code": "string (optional)"
        }

    セキュリティ:
        - 認証必須（ログインユーザーのみ利用可能）
        - CSRF保護
        - プロンプト最大長: 3000文字
    """
    try:
        # リクエストボディの解析
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': '無効なJSONフォーマットです',
                'code': 'INVALID_JSON'
            }, status=400)

        # プロンプトの取得
        user_prompt = data.get('prompt', '').strip()

        if not user_prompt:
            return JsonResponse({
                'status': 'error',
                'message': 'プロンプトを入力してください',
                'code': 'MISSING_PROMPT'
            }, status=400)

        # プロンプトの長さ制限（DoS対策）
        if len(user_prompt) > 3000:
            return JsonResponse({
                'status': 'error',
                'message': 'プロンプトは3000文字以内で入力してください',
                'code': 'PROMPT_TOO_LONG'
            }, status=400)

        # APIキーの取得
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key:
            logger.error("GEMINI_API_KEY is not configured")
            return JsonResponse({
                'status': 'error',
                'message': 'API設定が不正です。管理者に連絡してください。',
                'code': 'API_NOT_CONFIGURED'
            }, status=500)

        # プロンプト改善サービスの初期化と実行
        service = PromptImproverService(api_key=api_key)
        improved_prompt = service.improve_prompt(user_prompt)

        logger.info(
            f"Successfully improved prompt for user {request.user.id}. "
            f"Original length: {len(user_prompt)}, Improved length: {len(improved_prompt)}"
        )

        return JsonResponse({
            'status': 'success',
            'original_prompt': user_prompt,
            'improved_prompt': improved_prompt
        })

    except PromptImproverError as e:
        logger.error(f"Prompt improvement error for user {request.user.id}: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e),
            'code': 'IMPROVEMENT_FAILED'
        }, status=400)

    except Exception as e:
        logger.error(f"Unexpected error in improve_prompt for user {request.user.id}: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'プロンプトの改善中にエラーが発生しました',
            'code': 'INTERNAL_ERROR'
        }, status=500)
