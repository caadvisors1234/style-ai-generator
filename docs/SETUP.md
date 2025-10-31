# セットアップガイド

## Phase 0 完了状況

✅ 完了済み:
- Djangoプロジェクト作成
- アプリケーション作成（accounts, images, api）
- 依存パッケージインストール
- 環境変数設定（.env作成）
- Celery設定
- ASGI設定（WebSocket対応）
- ディレクトリ構造作成

⚠️ 追加セットアップが必要:
- PostgreSQL 14のインストールと起動
- Redis 7のインストールと起動
- Google Cloud認証情報の設定

## 必要な外部サービスのセットアップ

### 1. PostgreSQL 14のインストール

#### macOS (Homebrew使用)
```bash
# PostgreSQLインストール
brew install postgresql@14

# PostgreSQL起動
brew services start postgresql@14

# データベース作成
createdb image_conversion_db
```

#### Linux (Ubuntu/Debian)
```bash
# PostgreSQLインストール
sudo apt update
sudo apt install postgresql-14

# PostgreSQL起動
sudo systemctl start postgresql
sudo systemctl enable postgresql

# データベース作成
sudo -u postgres psql
CREATE DATABASE image_conversion_db;
CREATE USER postgres WITH PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE image_conversion_db TO postgres;
\q
```

### 2. Redisのインストール

#### macOS (Homebrew使用)
```bash
# Redisインストール
brew install redis

# Redis起動
brew services start redis

# 動作確認
redis-cli ping
# 「PONG」と返れば成功
```

#### Linux (Ubuntu/Debian)
```bash
# Redisインストール
sudo apt update
sudo apt install redis-server

# Redis起動
sudo systemctl start redis-server
sudo systemctl enable redis-server

# 動作確認
redis-cli ping
```

### 3. Google Cloud認証情報の設定

#### サービスアカウントキーの取得
1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. プロジェクトを作成または選択
3. Vertex AI APIを有効化
4. サービスアカウントを作成
5. キーをJSONファイルでダウンロード

#### .envファイルの更新
```bash
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
```

## 開発時の簡易セットアップ（オプション）

PostgreSQLとRedisがまだ準備できていない場合、以下で代用可能です：

### SQLiteを使用（開発環境のみ）
`config/settings.py` のDATABASES設定を一時的に変更：
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

### Celeryとキャッシュを無効化（開発環境のみ）
一時的にCeleryとRedisキャッシュをコメントアウト可能。

## 開発時の一括起動スクリプト

Celeryワーカー・Celery Beat・Django開発サーバー（Channels含む）を同時に起動するには、リポジトリ直下で以下を実行してください：

```bash
./scripts/run_all_services.sh
```

停止する際は `Ctrl+C` を押すと、起動したプロセスがまとめて終了します。

## 次のステップ

Phase 0が完了したので、Phase 1（基盤構築）に進みます：
- データベースモデルの作成
- マイグレーションの実行
- 管理コマンドの作成

## トラブルシューティング

### PostgreSQL接続エラー
```bash
# PostgreSQLが起動しているか確認
pg_isready

# PostgreSQLを再起動
brew services restart postgresql@14  # macOS
sudo systemctl restart postgresql    # Linux
```

### Redis接続エラー
```bash
# Redisが起動しているか確認
redis-cli ping

# Redisを再起動
brew services restart redis  # macOS
sudo systemctl restart redis-server  # Linux
```

### 依存パッケージエラー
```bash
# 依存パッケージを再インストール
pip3 install -r requirements.txt --force-reinstall
```
