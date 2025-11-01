"""
ヘルスチェックエンドポイント

本番環境での監視・ロードバランサー用
"""

from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
import os
import shutil


def health_check(request):
    """
    システムヘルスチェック

    GET /api/v1/health/

    Response:
        {
            "status": "healthy" | "unhealthy",
            "checks": {
                "database": "ok" | "error message",
                "cache": "ok" | "error message",
                "disk": {
                    "free_gb": 10.5,
                    "percent_used": 65.3
                }
            }
        }
    """
    health = {
        'status': 'healthy',
        'checks': {}
    }

    # データベース接続確認
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health['checks']['database'] = 'ok'
    except Exception as e:
        health['status'] = 'unhealthy'
        health['checks']['database'] = f'error: {str(e)}'

    # キャッシュ（Redis）接続確認
    try:
        cache.set('health_check', 'ok', 10)
        cache_value = cache.get('health_check')
        if cache_value == 'ok':
            health['checks']['cache'] = 'ok'
        else:
            health['status'] = 'unhealthy'
            health['checks']['cache'] = 'cache value mismatch'
    except Exception as e:
        health['status'] = 'unhealthy'
        health['checks']['cache'] = f'error: {str(e)}'

    # ディスク容量確認
    try:
        disk = shutil.disk_usage('/')
        free_gb = disk.free / (2**30)  # GBに変換
        percent_used = (disk.used / disk.total) * 100

        health['checks']['disk'] = {
            'free_gb': round(free_gb, 2),
            'percent_used': round(percent_used, 2)
        }

        # ディスク使用率が90%を超えたら警告
        if percent_used > 90:
            health['status'] = 'unhealthy'
            health['checks']['disk']['warning'] = 'disk usage > 90%'
    except Exception as e:
        health['checks']['disk'] = f'error: {str(e)}'

    # ステータスコード決定
    status_code = 200 if health['status'] == 'healthy' else 503

    return JsonResponse(health, status=status_code)


def readiness_check(request):
    """
    レディネスチェック（アプリケーション準備完了確認）

    GET /api/v1/ready/

    K8s等のオーケストレーションツール向け
    """
    # 最小限のチェック（データベース接続のみ）
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({'status': 'ready'}, status=200)
    except Exception as e:
        return JsonResponse({
            'status': 'not_ready',
            'error': str(e)
        }, status=503)


def liveness_check(request):
    """
    ライブネスチェック（プロセス生存確認）

    GET /api/v1/alive/

    K8s等のオーケストレーションツール向け
    """
    # プロセスが応答できればOK（最軽量チェック）
    return JsonResponse({'status': 'alive'}, status=200)
