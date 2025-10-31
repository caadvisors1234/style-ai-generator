# 技術スタック
- 言語: Python 3.11+
- Webフレームワーク: Django 5.0 系
- 非同期処理: Celery 5 + Redis 7 (channels_redis を含む)
- WebSocket: Django Channels 4 / daphne
- データベース: PostgreSQL 14 (開発では SQLite 代替可)
- 画像処理: Pillow, Vertex AI Gemini 2.5 Flash Image (google-genai / google-cloud-aiplatform)
- インフラ: Docker / docker-compose を前提
- ログ & キャッシュ: Redis キャッシュ、ファイルロギング (logs/django.log)
- その他: django-extensions, django-celery-beat