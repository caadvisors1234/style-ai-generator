"""
画像変換Celeryタスク

Google Gemini 2.5 Flash Image APIを使用した画像変換処理。
WebSocketを通じたリアルタイム進捗通知機能を含む。
"""

import os
import time
import logging
import uuid
from typing import Dict, Any
from decimal import Decimal

from celery import shared_task
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import ImageConversion, GeneratedImage
from .services.gemini_image_api import GeminiImageAPIService, GeminiImageAPIError


logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_image_conversion(self, conversion_id: int) -> Dict[str, Any]:
    """
    画像変換処理タスク

    Args:
        conversion_id (int): ImageConversionのID

    Returns:
        dict: 処理結果
    """
    logger.info(f"Starting image conversion task for ID: {conversion_id}")

    start_time = time.time()
    channel_layer = get_channel_layer()
    conversion_group = f'conversion_{conversion_id}'

    try:
        # ImageConversionレコードを取得
        conversion = ImageConversion.objects.get(id=conversion_id)

        # ステータスを処理中に更新
        conversion.mark_as_processing()

        # 進捗通知: 開始
        async_to_sync(channel_layer.group_send)(
            conversion_group,
            {
                'type': 'conversion_progress',
                'message': '画像変換を開始しています...',
                'progress': 10,
                'status': 'processing'
            }
        )

        # 元画像のパス
        original_image_path = conversion.original_image_path

        # 進捗通知: API呼び出し前
        async_to_sync(channel_layer.group_send)(
            conversion_group,
            {
                'type': 'conversion_progress',
                'message': 'AI画像生成中...',
                'progress': 30,
                'status': 'processing'
            }
        )

        # Gemini 2.5 Flash Imageで画像生成
        logger.info(f"Calling Gemini Image API with prompt: {conversion.prompt[:100]}...")

        generated_results = GeminiImageAPIService.generate_images_from_reference(
            original_image_path=original_image_path,
            prompt=conversion.prompt,
            generation_count=conversion.generation_count,
            aspect_ratio="4:3"  # デフォルトのアスペクト比
        )

        logger.info(f"Generated {len(generated_results)} images")

        # 進捗通知: 画像保存中
        async_to_sync(channel_layer.group_send)(
            conversion_group,
            {
                'type': 'conversion_progress',
                'message': '生成画像を保存中...',
                'progress': 70,
                'status': 'processing'
            }
        )

        # 生成画像を保存
        saved_images = []

        for idx, result in enumerate(generated_results, 1):
            # ファイル名生成
            filename = f"{uuid.uuid4()}.jpg"

            # 保存ディレクトリ
            output_dir = f"generated/user_{conversion.user.id}"

            # 画像を保存
            try:
                relative_path = GeminiImageAPIService.save_generated_image(
                    image_data=result['image_data'],
                    output_dir=output_dir,
                    filename=filename
                )

                # ファイルサイズ取得
                file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
                file_size = os.path.getsize(file_path)

                # GeneratedImageレコード作成
                generated_image = GeneratedImage.objects.create(
                    conversion=conversion,
                    image_path=relative_path,
                    image_name=filename,
                    image_size=file_size
                )

                saved_images.append({
                    'id': generated_image.id,
                    'url': f"/media/{relative_path}",
                    'name': filename,
                    'description': result.get('description', ''),
                })

                logger.info(f"Saved image {idx}/{len(generated_results)}: {relative_path}")

            except Exception as e:
                logger.error(f"Failed to save image {idx}: {str(e)}")
                # 一部失敗しても続行
                continue

        if not saved_images:
            raise GeminiImageAPIError("画像の保存に失敗しました")

        # 処理時間計算
        processing_time = Decimal(str(time.time() - start_time))

        # ステータスを完了に更新
        conversion.mark_as_completed(processing_time)

        # 進捗通知: 完了
        async_to_sync(channel_layer.group_send)(
            conversion_group,
            {
                'type': 'conversion_completed',
                'message': '画像変換が完了しました！',
                'images': saved_images
            }
        )

        logger.info(
            f"Image conversion completed for ID: {conversion_id}, "
            f"Processing time: {processing_time}s, "
            f"Generated images: {len(saved_images)}"
        )

        return {
            'status': 'success',
            'conversion_id': conversion_id,
            'images_count': len(saved_images),
            'processing_time': float(processing_time)
        }

    except ImageConversion.DoesNotExist:
        error_msg = f"ImageConversion with ID {conversion_id} does not exist"
        logger.error(error_msg)
        return {'status': 'error', 'message': error_msg}

    except GeminiImageAPIError as e:
        error_msg = str(e)
        logger.error(f"Gemini API error for conversion {conversion_id}: {error_msg}")

        # ステータスを失敗に更新
        try:
            conversion = ImageConversion.objects.get(id=conversion_id)
            conversion.mark_as_failed(error_msg)
        except Exception as update_error:
            logger.error(f"Failed to update conversion status: {update_error}")

        # 失敗通知
        async_to_sync(channel_layer.group_send)(
            conversion_group,
            {
                'type': 'conversion_failed',
                'message': '画像変換に失敗しました',
                'error': error_msg
            }
        )

        return {'status': 'error', 'message': error_msg}

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.exception(f"Unexpected error for conversion {conversion_id}")

        # リトライ
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying task (attempt {self.request.retries + 1})")
            raise self.retry(exc=e, countdown=60)  # 60秒後にリトライ

        # 最大リトライ回数を超えた場合
        try:
            conversion = ImageConversion.objects.get(id=conversion_id)
            conversion.mark_as_failed(error_msg)
        except Exception as update_error:
            logger.error(f"Failed to update conversion status: {update_error}")

        # 失敗通知
        async_to_sync(channel_layer.group_send)(
            conversion_group,
            {
                'type': 'conversion_failed',
                'message': '画像変換に失敗しました',
                'error': error_msg
            }
        )

        return {'status': 'error', 'message': error_msg}
