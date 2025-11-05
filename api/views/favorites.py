"""
お気に入りプロンプトAPI
"""
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction

from api.decorators import login_required_api
from images.models import PromptPreset, UserFavoritePrompt

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
@login_required_api
def favorites_list(request):
    """
    お気に入りプリセット一覧取得API

    GET /api/v1/prompts/favorites/

    Response:
        {
            "status": "success",
            "favorites": [
                {
                    "id": int,
                    "preset_id": int,
                    "name": "string",
                    "prompt": "string",
                    "category": "string",
                    "description": "string",
                    "created_at": "datetime"
                }
            ]
        }
    """
    try:
        favorites = UserFavoritePrompt.objects.filter(
            user=request.user
        ).select_related('preset').order_by('-created_at')

        favorites_data = [
            {
                'id': fav.id,
                'preset_id': fav.preset.id,
                'name': fav.preset.name,
                'prompt': fav.preset.prompt,
                'category': fav.preset.category,
                'description': fav.preset.description,
                'created_at': fav.created_at.isoformat()
            }
            for fav in favorites
        ]

        return JsonResponse({
            'status': 'success',
            'favorites': favorites_data
        })

    except Exception as e:
        logger.error(f"Favorites list error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'お気に入り一覧の取得中にエラーが発生しました'
        }, status=500)


@require_http_methods(["POST"])
@login_required_api
def favorites_add(request):
    """
    お気に入りプリセット追加API

    POST /api/v1/prompts/favorites/add/

    Request:
        {
            "preset_id": int
        }

    Response:
        {
            "status": "success",
            "message": "お気に入りに追加しました",
            "favorite_id": int
        }
    """
    try:
        import json
        data = json.loads(request.body)
        preset_id = data.get('preset_id')

        if not preset_id:
            return JsonResponse({
                'status': 'error',
                'message': 'プリセットIDは必須です'
            }, status=400)

        # プリセットの存在確認
        try:
            preset = PromptPreset.objects.get(id=preset_id, is_active=True)
        except PromptPreset.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'プリセットが見つかりません'
            }, status=404)

        # 既にお気に入りに追加されているか確認
        existing = UserFavoritePrompt.objects.filter(
            user=request.user,
            preset=preset
        ).first()

        if existing:
            return JsonResponse({
                'status': 'success',
                'message': '既にお気に入りに追加されています',
                'favorite_id': existing.id,
                'already_exists': True
            })

        # お気に入りに追加
        with transaction.atomic():
            favorite = UserFavoritePrompt.objects.create(
                user=request.user,
                preset=preset
            )

        logger.info(
            f"Favorite added: user={request.user.username}, "
            f"preset={preset.name}"
        )

        return JsonResponse({
            'status': 'success',
            'message': 'お気に入りに追加しました',
            'favorite_id': favorite.id,
            'already_exists': False
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': '無効なJSONデータです'
        }, status=400)

    except Exception as e:
        logger.error(f"Favorites add error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'お気に入り追加中にエラーが発生しました'
        }, status=500)


@require_http_methods(["POST", "DELETE"])
@login_required_api
def favorites_remove(request, preset_id):
    """
    お気に入りプリセット削除API

    POST/DELETE /api/v1/prompts/favorites/<preset_id>/remove/

    Response:
        {
            "status": "success",
            "message": "お気に入りから削除しました"
        }
    """
    try:
        # お気に入りを検索
        favorite = UserFavoritePrompt.objects.filter(
            user=request.user,
            preset_id=preset_id
        ).first()

        if not favorite:
            return JsonResponse({
                'status': 'error',
                'message': 'お気に入りが見つかりません'
            }, status=404)

        # 削除
        with transaction.atomic():
            favorite.delete()

        logger.info(
            f"Favorite removed: user={request.user.username}, "
            f"preset_id={preset_id}"
        )

        return JsonResponse({
            'status': 'success',
            'message': 'お気に入りから削除しました'
        })

    except Exception as e:
        logger.error(f"Favorites remove error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'お気に入り削除中にエラーが発生しました'
        }, status=500)
