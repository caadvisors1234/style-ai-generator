"""
アカウント関連Celeryタスク
"""

import logging
from celery import shared_task
from django.core.management import call_command


logger = logging.getLogger(__name__)


@shared_task
def reset_monthly_usage_task():
    """
    月次使用回数リセットタスク

    毎月1日0時0分に実行される定期タスク。
    全ユーザーの月次使用回数をリセットする。

    Returns:
        dict: 実行結果
    """
    logger.info("Starting monthly usage reset task")

    try:
        # 管理コマンドを実行
        call_command('reset_monthly_usage')

        logger.info("Monthly usage reset completed successfully")
        return {'status': 'success', 'message': 'Monthly usage reset completed'}

    except Exception as e:
        error_msg = f"Failed to reset monthly usage: {str(e)}"
        logger.error(error_msg)
        return {'status': 'error', 'message': error_msg}


@shared_task
def delete_expired_images_task():
    """
    期限切れ画像削除タスク

    毎日0時0分に実行される定期タスク。
    生成から30日経過した画像を削除する。

    Returns:
        dict: 実行結果
    """
    logger.info("Starting expired images deletion task")

    try:
        # 管理コマンドを実行
        call_command('delete_expired_images')

        logger.info("Expired images deletion completed successfully")
        return {'status': 'success', 'message': 'Expired images deletion completed'}

    except Exception as e:
        error_msg = f"Failed to delete expired images: {str(e)}"
        logger.error(error_msg)
        return {'status': 'error', 'message': error_msg}
