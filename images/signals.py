"""
imagesアプリのDjangoシグナル

モデルの変更時にキャッシュを自動的にクリアする。
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

from images.models import PromptPreset, ImageConversion


logger = logging.getLogger(__name__)


@receiver(post_save, sender=PromptPreset)
@receiver(post_delete, sender=PromptPreset)
def clear_prompt_cache(sender, instance, **kwargs):
    """
    PromptPresetの保存・削除時にプロンプト関連のキャッシュをクリア
    """
    try:
        # 全カテゴリのキャッシュをクリア
        cache.delete('prompts_list:all')
        cache.delete('prompts_categories')

        # 各カテゴリのキャッシュもクリア
        for category_value, _ in PromptPreset.CATEGORY_CHOICES:
            cache.delete(f'prompts_list:{category_value}')

        logger.info(f"Cleared prompt cache after {instance} changed")
    except Exception as e:
        logger.error(f"Error clearing prompt cache: {str(e)}")


@receiver(post_save, sender=ImageConversion)
@receiver(post_delete, sender=ImageConversion)
def clear_usage_cache(sender, instance, **kwargs):
    """
    ImageConversionの保存・削除時に利用状況キャッシュをクリア
    """
    try:
        user_id = instance.user_id

        # 該当ユーザーの利用状況キャッシュをクリア
        cache.delete(f'usage_summary:{user_id}')

        # 利用履歴キャッシュもクリア（1-12ヶ月分）
        for months in range(1, 13):
            cache.delete(f'usage_history:{user_id}:{months}')

        logger.info(f"Cleared usage cache for user {user_id} after ImageConversion changed")
    except Exception as e:
        logger.error(f"Error clearing usage cache: {str(e)}")
