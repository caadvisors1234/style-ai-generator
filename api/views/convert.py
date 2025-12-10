"""
画像変換API

画像変換の開始、進捗確認、キャンセルなどのエンドポイント。
"""

import logging
import os

from django.conf import settings
from django.db import transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.http import JsonResponse
from django.core.cache import cache
from django.views.decorators.http import require_http_methods

from api.decorators import login_required_api

from accounts.models import UserProfile
from images.models import ImageConversion, GeneratedImage
from images.tasks import process_image_conversion
from images.services.gemini_image_api import GeminiImageAPIService
from images.services.upload import ImageUploadService, UploadValidationError


logger = logging.getLogger(__name__)

MODEL_MULTIPLIERS = {
    'gemini-2.5-flash-image': 1,
    'gemini-3-pro-image-preview': 5,
}


@require_http_methods(["POST"])
@login_required_api
def convert_start(request):
    """
    画像変換開始API

    POST /api/v1/convert/

    Request (multipart/form-data):
        - image: File (required)
        - prompt: string (required)
        - generation_count: int (1-5, default: 1)
        - aspect_ratio: str (optional, supported ratio)

    Response (Success):
        {
            "status": "success",
            "conversion_id": int,
            "job_id": "string",
            "estimated_time": int (seconds)
        }

    Response (Error):
        {
            "status": "error",
            "message": "string"
        }
    """
    try:
        # ユーザープロファイル取得
        profile = request.user.profile

        # リクエストデータ取得
        image_file = request.FILES.get('image')
        prompt = request.POST.get('prompt')
        generation_count = int(request.POST.get('generation_count', 1))
        requested_model = request.POST.get('model_variant') or request.POST.get('model')
        model_name = requested_model or GeminiImageAPIService.DEFAULT_MODEL
        if model_name not in MODEL_MULTIPLIERS:
            model_name = GeminiImageAPIService.DEFAULT_MODEL
        usage_cost = generation_count * MODEL_MULTIPLIERS[model_name]

        aspect_ratio = request.POST.get('aspect_ratio') or GeminiImageAPIService.DEFAULT_ASPECT_RATIO
        preset_id_raw = request.POST.get('preset_id')
        preset_name = request.POST.get('preset_name')
        try:
            preset_id = int(preset_id_raw) if preset_id_raw is not None else None
        except ValueError:
            preset_id = None

        # バリデーション
        if not image_file:
            return JsonResponse({
                'status': 'error',
                'message': '画像ファイルは必須です'
            }, status=400)

        if not prompt:
            return JsonResponse({
                'status': 'error',
                'message': 'プロンプトは必須です'
            }, status=400)

        if generation_count < 1 or generation_count > 5:
            return JsonResponse({
                'status': 'error',
                'message': '生成数は1から5の間で指定してください'
            }, status=400)

        if aspect_ratio not in GeminiImageAPIService.SUPPORTED_ASPECT_RATIOS:
            return JsonResponse({
                'status': 'error',
                'message': '画像比率がサポート対象外です'
            }, status=400)

        # 月次利用制限チェック
        if not profile.can_generate(usage_cost):
            return JsonResponse({
                'status': 'error',
                'message': f'月次利用上限に達しています（残り: {profile.remaining}クレジット）'
            }, status=403)

        upload_service = ImageUploadService(user_id=request.user.id)

        try:
            upload_results = upload_service.process_uploads([image_file])
        except UploadValidationError as upload_error:
            error_payload = upload_error.args[0] if upload_error.args else str(upload_error)
            response_data = {'status': 'error'}
            if isinstance(error_payload, dict):
                response_data.update(error_payload)
                response_data.setdefault('message', 'アップロード処理中にエラーが発生しました')
            else:
                response_data['message'] = str(upload_error)
            return JsonResponse(response_data, status=400)

        if not upload_results:
            return JsonResponse({
                'status': 'error',
                'message': 'アップロード処理に失敗しました'
            }, status=400)

        upload_result = upload_results[0]

        with transaction.atomic():
            # ImageConversionレコード作成
            conversion = ImageConversion.objects.create(
                user=request.user,
                original_image_path=upload_result['file_path'],
                original_image_name=upload_result['file_name'],
                original_image_size=upload_result['file_size'],
                prompt=prompt,
                preset_id=preset_id,
                preset_name=preset_name,
                generation_count=generation_count,
                aspect_ratio=aspect_ratio,
                status='pending',
                model_name=model_name,
                usage_consumed=usage_cost,
            )

            # 利用回数を事前に増やす（タスク失敗時はロールバック）
            profile.increment_usage(usage_cost)

        # Celeryタスク投入
        task = process_image_conversion.delay(conversion.id)

        # 推定処理時間（秒）
        estimated_time = generation_count * 30  # 1枚あたり約30秒と仮定

        logger.info(
            f"Image conversion started: conversion_id={conversion.id}, "
            f"user={request.user.username}, count={generation_count}"
        )

        return JsonResponse({
            'status': 'success',
            'conversion_id': conversion.id,
            'job_id': conversion.job_id,
            'task_id': task.id,
            'estimated_time': estimated_time,
            'aspect_ratio': aspect_ratio,
            'model': model_name,
        })

    except ValueError:
        return JsonResponse({
            'status': 'error',
            'message': '無効な生成枚数です'
        }, status=400)

    except Exception as e:
        logger.error(f"Convert start error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': '変換開始処理中にエラーが発生しました'
        }, status=500)


@require_http_methods(["GET"])
@login_required_api
def convert_status(request, conversion_id):
    """
    変換進捗確認API

    GET /api/v1/convert/<conversion_id>/status/

    Response (Processing):
        {
            "status": "success",
            "conversion": {
                "id": int,
                "status": "pending" | "processing" | "completed" | "failed" | "cancelled",
                "created_at": "datetime",
                "updated_at": "datetime"
            }
        }

    Response (Completed):
        {
            "status": "success",
            "conversion": {
                "id": int,
                "status": "completed",
                "processing_time": float,
                "created_at": "datetime",
                "updated_at": "datetime"
            },
            "images": [
                {
                    "id": int,
                    "url": "string",
                    "name": "string",
                    "size": int
                }
            ]
        }

    Response (Failed):
        {
            "status": "success",
            "conversion": {
                "id": int,
                "status": "failed",
                "error_message": "string",
                "created_at": "datetime",
                "updated_at": "datetime"
            }
        }
    """
    try:
        # 権限チェック（自分の変換のみ）
        conversion = ImageConversion.objects.filter(
            id=conversion_id,
            user=request.user,
            is_deleted=False
        ).first()

        if not conversion:
            return JsonResponse({
                'status': 'error',
                'message': '変換データが見つかりません'
            }, status=404)

        current_generated = conversion.generated_images.filter(is_deleted=False).count()

        # 基本情報
        response_data = {
            'status': 'success',
            'conversion': {
                'id': conversion.id,
                'status': conversion.status,
                'model_name': conversion.model_name,
                'usage_consumed': conversion.usage_consumed,
                'created_at': conversion.created_at.isoformat(),
                'updated_at': conversion.updated_at.isoformat(),
                'generation_count': conversion.generation_count,
                'current_count': current_generated,
                'aspect_ratio': conversion.aspect_ratio,
            }
        }

        fallback_info = cache.get(f"conversion_fallback_{conversion.id}")
        if fallback_info:
            response_data['conversion']['fallback'] = fallback_info

        # ステータスごとの追加情報
        if conversion.status == 'completed':
            # 生成画像一覧を取得
            generated_images = conversion.generated_images.filter(
                is_deleted=False
            ).order_by('created_at')

            response_data['conversion']['processing_time'] = float(conversion.processing_time)
            response_data['images'] = [
                {
                    'id': img.id,
                    'url': f"/media/{img.image_path}",
                    'name': img.image_name,
                    'size': img.image_size,
                    'created_at': img.created_at.isoformat()
                }
                for img in generated_images
            ]

        elif conversion.status == 'failed':
            response_data['conversion']['error_message'] = conversion.error_message

        return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"Convert status error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'ステータス取得中にエラーが発生しました'
        }, status=500)


@require_http_methods(["POST"])
@login_required_api
def convert_cancel(request, conversion_id):
    """
    変換キャンセルAPI

    POST /api/v1/convert/<conversion_id>/cancel/

    Response:
        {
            "status": "success",
            "message": "変換をキャンセルしました"
        }
    """
    try:
        with transaction.atomic():
            conversion = (
                ImageConversion.objects.select_for_update()
                .select_related('user')
                .filter(
                    id=conversion_id,
                    user=request.user,
                    is_deleted=False,
                )
                .first()
            )

            if not conversion:
                return JsonResponse({
                    'status': 'error',
                    'message': '変換データが見つかりません'
                }, status=404)

            if conversion.status == 'cancelled':
                return JsonResponse({
                    'status': 'success',
                    'message': 'この変換は既にキャンセルされています',
                    'result': 'already_cancelled'
                })

            if conversion.status in ['completed', 'failed']:
                return JsonResponse({
                    'status': 'success',
                    'message': 'この変換は既に処理済みです',
                    'result': 'already_finished'
                })

            # キャンセル可能なステータスチェック
            if conversion.status not in ['pending', 'processing']:
                return JsonResponse({
                    'status': 'error',
                    'message': 'この変換はキャンセルできません'
                }, status=400)

            conversion.mark_as_cancelled()

            # 利用枚数をロールバック
            profile = None
            try:
                profile = conversion.user.profile
            except UserProfile.DoesNotExist:
                profile = None

            if profile:
                profile_model = profile.__class__
                updated = profile_model.objects.filter(pk=profile.pk).update(
                    monthly_used=Greatest(
                        F('monthly_used') - conversion.usage_consumed,
                        Value(0),
                    )
                )
                if updated:
                    profile.refresh_from_db(fields=['monthly_used'])
                    if hasattr(profile, "invalidate_usage_cache"):
                        profile.invalidate_usage_cache()

            # 既に生成されている画像があれば削除
            generated_images = list(conversion.generated_images.filter(is_deleted=False))
            removed_images = 0
            for image in generated_images:
                absolute_path = os.path.join(settings.MEDIA_ROOT, image.image_path)
                try:
                    if os.path.exists(absolute_path):
                        os.remove(absolute_path)
                except OSError as cleanup_error:
                    logger.warning(
                        "Failed to remove generated image file %s during cancel: %s",
                        absolute_path,
                        cleanup_error,
                    )
                image.delete()
                removed_images += 1

        logger.info(
            "Conversion cancelled: conversion_id=%s, removed_images=%s",
            conversion_id,
            removed_images,
        )

        return JsonResponse({
            'status': 'success',
            'message': '変換をキャンセルしました'
        })

    except Exception as e:
        logger.error(f"Convert cancel error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'キャンセル処理中にエラーが発生しました'
        }, status=500)
