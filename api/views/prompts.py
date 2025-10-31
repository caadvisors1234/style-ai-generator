"""
プロンプトプリセットAPI

プリセットプロンプトの一覧取得など。
"""

import logging
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.core.cache import cache
from django.views.decorators.cache import cache_page

from images.models import PromptPreset


logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
@cache_page(60 * 60)  # 1時間キャッシュ
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
                    "display_order": int
                }
            ]
        }
    """
    try:
        category = request.GET.get('category')

        # キャッシュキー
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
