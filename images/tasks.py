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
from django.db import transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.core.cache import cache
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import ImageConversion, GeneratedImage
from .services.gemini_image_api import GeminiImageAPIService, GeminiImageAPIError


logger = logging.getLogger(__name__)

MODEL_MULTIPLIERS = {
    'gemini-2.5-flash-image': 1,
    'gemini-3-pro-image-preview': 5,
}


class ConversionCancelledError(Exception):
    """Raised when a conversion has been cancelled by the user."""


def _ensure_not_cancelled(conversion: ImageConversion) -> None:
    """Reload conversion status and abort if it has been cancelled."""

    conversion.refresh_from_db(fields=['status'])
    if conversion.status == 'cancelled':
        raise ConversionCancelledError(f"Conversion {conversion.id} has been cancelled")


def _remove_file_if_exists(path: str) -> None:
    """Remove a file from disk if it exists."""

    if not path:
        return
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError as error:
        logger.warning("Failed to remove file %s: %s", path, error)


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
    conversion = None
    saved_records = []

    try:
        with transaction.atomic():
            conversion = (
                ImageConversion.objects.select_for_update()
                .get(id=conversion_id)
            )
            saved_records = []

            if conversion.status == 'cancelled':
                raise ConversionCancelledError(
                    f"Conversion {conversion.id} has been cancelled"
                )

            if conversion.status in ['completed', 'failed']:
                logger.info(
                    "Conversion %s already finished with status %s. Skipping.",
                    conversion.id,
                    conversion.status,
                )
                return {
                    'status': conversion.status,
                    'message': 'Conversion already finished before processing task.',
                }

            if conversion.status != 'processing':
                conversion.mark_as_processing()

            # 前回のフォールバック通知をクリア
            cache.delete(f"conversion_fallback_{conversion.id}")

        _ensure_not_cancelled(conversion)

        # 進捗通知: 開始
        async_to_sync(channel_layer.group_send)(
            conversion_group,
            {
                'type': 'conversion_progress',
                'message': '画像変換を開始しています...',
                'progress': 10,
                'status': 'processing',
                'current': 0,
                'total': conversion.generation_count
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
                'status': 'processing',
                'current': 0,
                'total': conversion.generation_count
            }
        )

        # Gemini 2.5 Flash Imageで画像生成
        logger.info(f"Calling Gemini Image API with prompt: {conversion.prompt[:100]}...")

        _ensure_not_cancelled(conversion)

        requested_model = conversion.model_name

        generated_results, model_used = GeminiImageAPIService.generate_images_from_reference(
            original_image_path=original_image_path,
            prompt=conversion.prompt,
            generation_count=conversion.generation_count,
            aspect_ratio=conversion.aspect_ratio,
            model_name=conversion.model_name,
        )

        _ensure_not_cancelled(conversion)

        # 実際に使用されたモデルごとの内訳を集計（部分的フォールバック対応）
        used_models = [
            result.get('model_used') or model_used or requested_model
            for result in generated_results
        ]
        model_usage_counts: Dict[str, int] = {}
        for m in used_models:
            model_usage_counts[m] = model_usage_counts.get(m, 0) + 1

        actual_cost = sum(MODEL_MULTIPLIERS.get(m, 1) for m in used_models)
        fallback_present = any(m != requested_model for m in used_models)

        if fallback_present:
            actual_models = set(used_models)
            effective_model = used_models[0] if len(actual_models) == 1 else requested_model
            used_model_label = effective_model if len(actual_models) == 1 else 'mixed'
            refund = max(0, conversion.usage_consumed - actual_cost)

            # usage_consumed と必要なら model_name を補正
            update_fields = ['usage_consumed', 'updated_at']
            conversion.usage_consumed = actual_cost
            if len(actual_models) == 1 and effective_model != conversion.model_name:
                conversion.model_name = effective_model
                update_fields.append('model_name')
            conversion.save(update_fields=update_fields)

            # クレジット返却
            if refund > 0:
                try:
                    profile = conversion.user.profile
                    profile_model = profile.__class__
                    updated = profile_model.objects.filter(pk=profile.pk).update(
                        monthly_used=Greatest(
                            F('monthly_used') - refund,
                            Value(0),
                        )
                    )
                    if updated:
                        profile.refresh_from_db(fields=['monthly_used'])
                        if hasattr(profile, "invalidate_usage_cache"):
                            profile.invalidate_usage_cache()
                    logger.info(
                        "Adjusted usage after partial fallback: refund=%s, actual_cost=%s, models=%s",
                        refund,
                        actual_cost,
                        model_usage_counts,
                    )
                except Exception as refund_error:
                    logger.error(
                        "Failed to adjust usage after partial fallback: %s",
                        refund_error,
                    )

            fallback_payload = {
                'fallback': True,
                'requested_model': requested_model,
                'used_model': used_model_label,
                'refund': refund,
                'usage_consumed': actual_cost,
                'model_breakdown': model_usage_counts,
            }

            # WebSocket通知
            async_to_sync(channel_layer.group_send)(
                conversion_group,
                {
                    'type': 'conversion_progress',
                    'message': f"{requested_model} が利用できなかったため別モデルで生成しました。消費クレジットを再計算しています。",
                    'progress': 35,
                    'status': 'processing',
                    **fallback_payload,
                }
            )

            # ポーリング用にキャッシュへ記録（1時間保持）
            cache.set(
                f"conversion_fallback_{conversion.id}",
                fallback_payload,
                timeout=3600,
            )

        logger.info(f"Generated {len(generated_results)} images")

        # 進捗通知: 画像保存中
        async_to_sync(channel_layer.group_send)(
            conversion_group,
            {
                'type': 'conversion_progress',
                'message': '生成画像を保存中...',
                'progress': 70,
                'status': 'processing',
                'current': 0,
                'total': conversion.generation_count
            }
        )

        # 生成画像を保存
        saved_images = []

        for idx, result in enumerate(generated_results, 1):
            _ensure_not_cancelled(conversion)

            filename = f"{uuid.uuid4()}.jpg"
            output_dir = f"generated/user_{conversion.user.id}"

            relative_path = None
            file_path = None

            try:
                _ensure_not_cancelled(conversion)
                relative_path = GeminiImageAPIService.save_generated_image(
                    image_data=result['image_data'],
                    output_dir=output_dir,
                    filename=filename
                )

                file_path = os.path.join(settings.MEDIA_ROOT, relative_path)

                _ensure_not_cancelled(conversion)

                file_size = os.path.getsize(file_path)

                _ensure_not_cancelled(conversion)

                generated_image = GeneratedImage.objects.create(
                    conversion=conversion,
                    image_path=relative_path,
                    image_name=filename,
                    image_size=file_size
                )

                saved_records.append({
                    'instance': generated_image,
                    'file_path': file_path,
                })

                saved_images.append({
                    'id': generated_image.id,
                    'url': f"/media/{relative_path}",
                    'name': filename,
                    'description': result.get('description', ''),
                })

                logger.info(
                    "Saved image %s/%s: %s",
                    idx,
                    len(generated_results),
                    relative_path,
                )

                # 進捗通知: 画像保存進捗（70%から90%の間で更新）
                progress = 70 + int((idx / len(generated_results)) * 20)
                async_to_sync(channel_layer.group_send)(
                    conversion_group,
                    {
                        'type': 'conversion_progress',
                        'message': f'生成画像を保存中... ({idx}/{len(generated_results)})',
                        'progress': progress,
                        'status': 'processing',
                        'current': idx,
                        'total': len(generated_results)
                    }
                )

            except ConversionCancelledError:
                if file_path:
                    _remove_file_if_exists(file_path)
                elif relative_path:
                    _remove_file_if_exists(os.path.join(settings.MEDIA_ROOT, relative_path))
                raise
            except Exception as e:
                logger.error(f"Failed to save image {idx}: {str(e)}")
                _remove_file_if_exists(file_path)
                # 一部失敗しても続行
                continue

        _ensure_not_cancelled(conversion)

        if not saved_images:
            raise GeminiImageAPIError("画像の保存に失敗しました")

        # 処理時間計算
        processing_time = Decimal(str(time.time() - start_time))

        _ensure_not_cancelled(conversion)

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

    except ConversionCancelledError:
        logger.info("Conversion %s cancelled. Cleaning up partial results.", conversion_id)

        for record in saved_records:
            _remove_file_if_exists(record.get('file_path'))
            image_instance = record.get('instance')
            if image_instance:
                try:
                    image_instance.delete()
                except Exception as delete_error:
                    logger.warning(
                        "Failed to delete GeneratedImage %s during cancel cleanup: %s",
                        getattr(image_instance, 'id', 'unknown'),
                        delete_error,
                    )

        if conversion is None:
            try:
                conversion = ImageConversion.objects.get(id=conversion_id)
            except ImageConversion.DoesNotExist:
                conversion = None

        if conversion:
            conversion.refresh_from_db(fields=['status'])
            if conversion.status != 'cancelled':
                conversion.mark_as_cancelled()

        async_to_sync(channel_layer.group_send)(
            conversion_group,
            {
                'type': 'conversion_cancelled',
                'message': '画像変換はキャンセルされました'
            }
        )

        return {'status': 'cancelled', 'message': 'Conversion was cancelled'}

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
            try:
                profile = conversion.user.profile
                profile_model = profile.__class__
                updated = profile_model.objects.filter(pk=profile.pk).update(
                    monthly_used=Greatest(
                        F('monthly_used') - conversion.usage_consumed,
                        Value(0),
                    )
                )
                if not updated:
                    raise ValueError("No rows updated during usage rollback")
                profile.refresh_from_db(fields=['monthly_used'])
                if hasattr(profile, "invalidate_usage_cache"):
                    profile.invalidate_usage_cache()
                logger.info(
                    "Rolled back usage for user %s by %s",
                    profile.user_id,
                    conversion.usage_consumed,
                )
            except Exception as rollback_error:
                logger.error(
                    "Failed to rollback usage count for conversion %s: %s",
                    conversion_id,
                    rollback_error,
                )
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
            try:
                profile = conversion.user.profile
                profile_model = profile.__class__
                updated = profile_model.objects.filter(pk=profile.pk).update(
                    monthly_used=Greatest(
                        F('monthly_used') - conversion.usage_consumed,
                        Value(0),
                    )
                )
                if not updated:
                    raise ValueError("No rows updated during usage rollback")
                profile.refresh_from_db(fields=['monthly_used'])
                if hasattr(profile, "invalidate_usage_cache"):
                    profile.invalidate_usage_cache()
                logger.info(
                    "Rolled back usage for user %s by %s",
                    profile.user_id,
                    conversion.usage_consumed,
                )
            except Exception as rollback_error:
                logger.error(
                    "Failed to rollback usage count for conversion %s: %s",
                    conversion_id,
                    rollback_error,
                )
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
