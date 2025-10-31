"""
画像変換API

画像変換の開始、進捗確認、キャンセルなどのエンドポイント。
"""

import logging
import json
import os
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.conf import settings
from django.db import transaction
from api.decorators import login_required_api

from images.models import ImageConversion, GeneratedImage
from images.tasks import process_image_conversion


logger = logging.getLogger(__name__)


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
                'message': '生成枚数は1から5の間で指定してください'
            }, status=400)

        # ファイルサイズチェック（10MB）
        max_size = 10 * 1024 * 1024
        if image_file.size > max_size:
            return JsonResponse({
                'status': 'error',
                'message': 'ファイルサイズは10MB以下にしてください'
            }, status=400)

        # ファイル形式チェック
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.webp']
        file_ext = os.path.splitext(image_file.name)[1].lower()
        if file_ext not in allowed_extensions:
            return JsonResponse({
                'status': 'error',
                'message': '対応している形式はJPEG、PNG、WebPです'
            }, status=400)

        # 月次利用制限チェック
        if not profile.can_generate(generation_count):
            return JsonResponse({
                'status': 'error',
                'message': f'月次利用上限に達しています（残り: {profile.remaining}枚）'
            }, status=403)

        with transaction.atomic():
            # ファイル保存
            import uuid
            filename = f"{uuid.uuid4()}{file_ext}"
            relative_path = f"uploads/user_{request.user.id}/{filename}"

            # ディレクトリ作成
            file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # ファイル保存
            with open(file_path, 'wb+') as destination:
                for chunk in image_file.chunks():
                    destination.write(chunk)

            # ImageConversionレコード作成
            conversion = ImageConversion.objects.create(
                user=request.user,
                original_image_path=relative_path,
                original_image_name=image_file.name,
                original_image_size=image_file.size,
                prompt=prompt,
                generation_count=generation_count,
                status='pending'
            )

            # 利用回数を事前に増やす（タスク失敗時はロールバック）
            profile.increment_usage(generation_count)

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
            'estimated_time': estimated_time
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

        # 基本情報
        response_data = {
            'status': 'success',
            'conversion': {
                'id': conversion.id,
                'status': conversion.status,
                'created_at': conversion.created_at.isoformat(),
                'updated_at': conversion.updated_at.isoformat()
            }
        }

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

        # キャンセル可能なステータスチェック
        if conversion.status not in ['pending', 'processing']:
            return JsonResponse({
                'status': 'error',
                'message': 'この変換はキャンセルできません'
            }, status=400)

        # ステータス更新
        conversion.mark_as_cancelled()

        # Celeryタスクは自動的に停止を検知する仕組みが必要
        # （現在の実装では、タスク内でステータスをチェックする必要がある）

        logger.info(f"Conversion cancelled: conversion_id={conversion_id}")

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
