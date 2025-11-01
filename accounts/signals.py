"""
accountsアプリのDjangoシグナル

モデルの変更時にキャッシュを自動的にクリアする。
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

from accounts.models import UserProfile


logger = logging.getLogger(__name__)


@receiver(post_save, sender=UserProfile)
@receiver(post_delete, sender=UserProfile)
def clear_user_profile_cache(sender, instance, **kwargs):
    """
    UserProfileの保存・削除時に利用状況キャッシュをクリア
    """
    try:
        user_id = instance.user_id

        # 該当ユーザーの利用状況キャッシュをクリア
        cache.delete(f'usage_summary:{user_id}')

        # 利用履歴キャッシュもクリア（1-12ヶ月分）
        for months in range(1, 13):
            cache.delete(f'usage_history:{user_id}:{months}')

        logger.info(f"Cleared usage cache for user {user_id} after UserProfile changed")
    except Exception as e:
        logger.error(f"Error clearing user profile cache: {str(e)}")
