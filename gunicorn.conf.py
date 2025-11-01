"""
Gunicorn設定ファイル

本番環境用のWSGIサーバー設定
"""

import multiprocessing
import os

# サーバーソケット
bind = "0.0.0.0:8000"
backlog = 2048

# ワーカープロセス
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
max_requests = 1000  # メモリリーク対策
max_requests_jitter = 50  # ランダム性を追加

# タイムアウト
timeout = 30
graceful_timeout = 30
keepalive = 2

# デバッグ
reload = os.getenv('GUNICORN_RELOAD', 'False') == 'True'  # 開発時のみTrue
reload_engine = 'auto'

# ログ設定
accesslog = os.getenv('GUNICORN_ACCESS_LOG', 'logs/gunicorn_access.log')
errorlog = os.getenv('GUNICORN_ERROR_LOG', 'logs/gunicorn_error.log')
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# プロセス管理
daemon = False  # supervisord/systemdで管理するためFalse
pidfile = os.getenv('GUNICORN_PID_FILE', 'logs/gunicorn.pid')
user = None  # Dockerコンテナ内では指定不要
group = None

# サーバーフック
def on_starting(server):
    """Gunicorn起動時"""
    server.log.info("=== Gunicorn starting ===")


def on_reload(server):
    """リロード時"""
    server.log.info("=== Gunicorn reloading ===")


def when_ready(server):
    """準備完了時"""
    server.log.info("=== Gunicorn ready ===")


def on_exit(server):
    """終了時"""
    server.log.info("=== Gunicorn exiting ===")


def worker_int(worker):
    """ワーカーがSIGINT受信時"""
    worker.log.info(f"Worker {worker.pid} received SIGINT")


def worker_abort(worker):
    """ワーカーがタイムアウト時"""
    worker.log.warning(f"Worker {worker.pid} timed out")


def pre_fork(server, worker):
    """ワーカーフォーク前"""
    pass


def post_fork(server, worker):
    """ワーカーフォーク後"""
    server.log.info(f"Worker {worker.pid} spawned")


def post_worker_init(worker):
    """ワーカー初期化後"""
    pass


def worker_exit(server, worker):
    """ワーカー終了時"""
    server.log.info(f"Worker {worker.pid} exited")


def child_exit(server, worker):
    """子プロセス終了時"""
    pass


def nworkers_changed(server, new_value, old_value):
    """ワーカー数変更時"""
    server.log.info(f"Workers changed from {old_value} to {new_value}")
