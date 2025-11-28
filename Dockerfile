# Python 3.11ベースイメージ
FROM python:3.11-slim

# 環境変数設定
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 作業ディレクトリ設定
WORKDIR /app

# システムパッケージのインストール
RUN apt-get update && apt-get install -y \
    postgresql-client \
    netcat-openbsd \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Pythonパッケージのインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードのコピー
COPY . .

# ログディレクトリ作成
RUN mkdir -p /app/logs /app/staticfiles /app/media

# 実行権限付与
RUN chmod +x /app/docker-entrypoint.sh || true

# ポート公開
EXPOSE 8000

# エントリーポイント設定
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
