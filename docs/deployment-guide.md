# デプロイ・運用手順書

**プロジェクト**: 美容室画像変換システム
**バージョン**: 1.0
**最終更新**: 2025-11-01

---

## 目次

1. [本番環境要件](#本番環境要件)
2. [初回デプロイ手順](#初回デプロイ手順)
3. [更新デプロイ手順](#更新デプロイ手順)
4. [バックアップ・リストア手順](#バックアップリストア手順)
5. [監視・メンテナンス](#監視メンテナンス)
6. [トラブルシューティング](#トラブルシューティング)

---

## 本番環境要件

### システム要件
- **OS**: Ubuntu 22.04 LTS以降 / Debian 11以降
- **CPU**: 4コア以上推奨
- **メモリ**: 8GB以上推奨
- **ディスク**: 50GB以上（ログ・メディアファイル用に追加容量必要）

### 必須ソフトウェア
- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Nginx 1.18+
- Node.js 18+ （フロントエンドビルド用）
- Git

### オプション
- Docker & Docker Compose（コンテナデプロイの場合）
- Supervisor / Systemd（プロセス管理）
- Let's Encrypt Certbot（SSL証明書）

---

## 初回デプロイ手順

### 1. サーバーセットアップ

#### システム更新
```bash
sudo apt update && sudo apt upgrade -y
```

#### 必須パッケージインストール
```bash
sudo apt install -y python3.11 python3.11-venv python3-pip \
    postgresql postgresql-contrib redis-server nginx git \
    build-essential libpq-dev
```

### 2. PostgreSQLセットアップ

```bash
# PostgreSQLサービス起動
sudo systemctl start postgresql
sudo systemctl enable postgresql

# データベース作成
sudo -u postgres psql <<EOF
CREATE DATABASE image_conversion_db;
CREATE USER imageconv_user WITH PASSWORD 'your_strong_password_here';
ALTER ROLE imageconv_user SET client_encoding TO 'utf8';
ALTER ROLE imageconv_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE imageconv_user SET timezone TO 'Asia/Tokyo';
GRANT ALL PRIVILEGES ON DATABASE image_conversion_db TO imageconv_user;
\q
EOF
```

### 3. Redisセットアップ

```bash
# Redis起動
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Redis接続確認
redis-cli ping  # PONG が返ればOK
```

### 4. アプリケーションデプロイ

#### プロジェクトクローン
```bash
cd /var/www
sudo git clone https://github.com/your-org/style-ai-generator.git
cd style-ai-generator
sudo chown -R $USER:$USER .
```

#### Python仮想環境作成
```bash
python3.11 -m venv venv
source venv/bin/activate
```

#### 依存パッケージインストール
```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

#### 環境変数設定
```bash
cp .env.example .env
nano .env
```

**`.env`設定例**:
```bash
# Django設定
SECRET_KEY=your-very-long-random-secret-key-here-50-characters-minimum
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# データベース
DATABASE_URL=postgresql://imageconv_user:your_strong_password_here@localhost:5432/image_conversion_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Google Cloud (Vertex AI)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1

# ログ設定
GUNICORN_ACCESS_LOG=/var/log/style-ai-generator/gunicorn_access.log
GUNICORN_ERROR_LOG=/var/log/style-ai-generator/gunicorn_error.log
```

#### ログディレクトリ作成
```bash
sudo mkdir -p /var/log/style-ai-generator
sudo chown $USER:$USER /var/log/style-ai-generator
mkdir -p logs
```

#### 静的ファイル・メディアディレクトリ作成
```bash
mkdir -p staticfiles media
```

#### データベースマイグレーション
```bash
python manage.py migrate
```

#### 静的ファイル収集
```bash
python manage.py collectstatic --noinput
```

#### スーパーユーザー作成
```bash
python manage.py createsuperuser
```

#### プリセットデータ読み込み
```bash
python manage.py loaddata images/fixtures/prompts.json
```

### 5. Gunicorn設定（Systemd）

`/etc/systemd/system/gunicorn.service`:
```ini
[Unit]
Description=Gunicorn daemon for Style AI Generator
After=network.target

[Service]
User=your_user
Group=www-data
WorkingDirectory=/var/www/style-ai-generator
Environment="PATH=/var/www/style-ai-generator/venv/bin"
ExecStart=/var/www/style-ai-generator/venv/bin/gunicorn \
          --config /var/www/style-ai-generator/gunicorn.conf.py \
          config.wsgi:application

[Install]
WantedBy=multi-user.target
```

### 6. Celery設定（Systemd）

`/etc/systemd/system/celery-worker.service`:
```ini
[Unit]
Description=Celery Worker for Style AI Generator
After=network.target redis.service

[Service]
Type=forking
User=your_user
Group=www-data
WorkingDirectory=/var/www/style-ai-generator
Environment="PATH=/var/www/style-ai-generator/venv/bin"
ExecStart=/var/www/style-ai-generator/venv/bin/celery -A config worker \
          --loglevel=info \
          --pidfile=/var/run/celery/worker.pid \
          --logfile=/var/log/style-ai-generator/celery_worker.log
PIDFile=/var/run/celery/worker.pid

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/celery-beat.service`:
```ini
[Unit]
Description=Celery Beat for Style AI Generator
After=network.target redis.service

[Service]
Type=forking
User=your_user
Group=www-data
WorkingDirectory=/var/www/style-ai-generator
Environment="PATH=/var/www/style-ai-generator/venv/bin"
ExecStart=/var/www/style-ai-generator/venv/bin/celery -A config beat \
          --loglevel=info \
          --pidfile=/var/run/celery/beat.pid \
          --logfile=/var/log/style-ai-generator/celery_beat.log \
          --schedule=/var/run/celery/celerybeat-schedule
PIDFile=/var/run/celery/beat.pid

[Install]
WantedBy=multi-user.target
```

```bash
# Celery用ディレクトリ作成
sudo mkdir -p /var/run/celery
sudo chown your_user:www-data /var/run/celery

# サービス有効化・起動
sudo systemctl daemon-reload
sudo systemctl enable gunicorn celery-worker celery-beat
sudo systemctl start gunicorn celery-worker celery-beat
```

### 7. Nginx設定

```bash
# 設定ファイルコピー
sudo cp nginx/nginx.conf /etc/nginx/sites-available/style-ai-generator

# シンボリックリンク作成
sudo ln -s /etc/nginx/sites-available/style-ai-generator /etc/nginx/sites-enabled/

# デフォルト設定削除
sudo rm /etc/nginx/sites-enabled/default

# 設定テスト
sudo nginx -t

# Nginx再起動
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### 8. SSL証明書設定（Let's Encrypt）

```bash
# Certbotインストール
sudo apt install -y certbot python3-certbot-nginx

# 証明書取得
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# 自動更新設定確認
sudo systemctl status certbot.timer
```

### 9. ファイアウォール設定

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### 10. 初回デプロイ確認

```bash
# サービス状態確認
sudo systemctl status gunicorn
sudo systemctl status celery-worker
sudo systemctl status celery-beat
sudo systemctl status nginx

# ヘルスチェック
curl http://localhost:8000/api/v1/health/

# HTTPSアクセス確認
curl https://yourdomain.com/api/v1/health/
```

---

## 更新デプロイ手順

### 自動デプロイスクリプト使用

```bash
cd /var/www/style-ai-generator
./scripts/deploy.sh main
```

### 手動デプロイ

```bash
cd /var/www/style-ai-generator
source venv/bin/activate

# 1. バックアップ
./scripts/backup.sh

# 2. 最新コード取得
git pull origin main

# 3. 依存パッケージ更新
pip install -r requirements.txt --upgrade

# 4. マイグレーション
python manage.py migrate

# 5. 静的ファイル収集
python manage.py collectstatic --noinput

# 6. サービス再起動
sudo systemctl restart gunicorn celery-worker celery-beat
sudo systemctl reload nginx

# 7. ヘルスチェック
curl http://localhost:8000/api/v1/health/
```

---

## バックアップ・リストア手順

### バックアップ

#### 自動バックアップ設定（Cron）
```bash
crontab -e
```

```cron
# 毎日午前2時にバックアップ実行
0 2 * * * /var/www/style-ai-generator/scripts/backup.sh
```

#### 手動バックアップ
```bash
cd /var/www/style-ai-generator
./scripts/backup.sh
```

バックアップファイルは `/var/backups/style-ai-generator/` に保存されます：
- `db_YYYYMMDD_HHMMSS.sql.gz` - データベース
- `media_YYYYMMDD_HHMMSS.tar.gz` - メディアファイル
- `config_YYYYMMDD_HHMMSS.tar.gz` - 設定ファイル

### リストア

#### データベースリストア
```bash
gunzip -c /var/backups/style-ai-generator/db_20251101_020000.sql.gz | \
    psql postgresql://imageconv_user:password@localhost:5432/image_conversion_db
```

#### メディアファイルリストア
```bash
cd /var/www/style-ai-generator
tar -xzf /var/backups/style-ai-generator/media_20251101_020000.tar.gz
```

---

## 監視・メンテナンス

### ログ確認

```bash
# Gunicornログ
tail -f /var/log/style-ai-generator/gunicorn_access.log
tail -f /var/log/style-ai-generator/gunicorn_error.log

# Celeryログ
tail -f /var/log/style-ai-generator/celery_worker.log
tail -f /var/log/style-ai-generator/celery_beat.log

# Nginxログ
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 月次メンテナンスタスク

1. **ディスク容量確認**
   ```bash
   df -h
   du -sh /var/www/style-ai-generator/media
   du -sh /var/backups/style-ai-generator
   ```

2. **古いログ削除**
   ```bash
   find /var/log/style-ai-generator -name "*.log" -mtime +90 -delete
   ```

3. **期限切れ画像削除**（自動実行されますが、手動確認も可）
   ```bash
   python manage.py delete_expired_images
   ```

4. **月次利用状況リセット**（自動実行されますが、手動確認も可）
   ```bash
   python manage.py reset_monthly_usage
   ```

5. **データベース統計更新**
   ```bash
   sudo -u postgres psql image_conversion_db -c "VACUUM ANALYZE;"
   ```

---

## トラブルシューティング

### 問題: Gunicornが起動しない

```bash
# ログ確認
sudo journalctl -u gunicorn -n 50 --no-pager

# 設定テスト
cd /var/www/style-ai-generator
source venv/bin/activate
gunicorn --config gunicorn.conf.py config.wsgi:application --check-config
```

### 問題: Celeryワーカーが動作しない

```bash
# ログ確認
tail -f /var/log/style-ai-generator/celery_worker.log

# Redis接続確認
redis-cli ping

# 手動起動テスト
cd /var/www/style-ai-generator
source venv/bin/activate
celery -A config worker --loglevel=debug
```

### 問題: データベース接続エラー

```bash
# PostgreSQL状態確認
sudo systemctl status postgresql

# 接続テスト
psql postgresql://imageconv_user:password@localhost:5432/image_conversion_db

# Django接続テスト
cd /var/www/style-ai-generator
source venv/bin/activate
python manage.py dbshell
```

### 問題: 静的ファイルが表示されない

```bash
# 静的ファイル再収集
python manage.py collectstatic --clear --noinput

# Nginx設定確認
sudo nginx -t

# パーミッション確認
ls -la /var/www/style-ai-generator/staticfiles/
```

### 問題: ディスク容量不足

```bash
# 容量確認
df -h

# 大きなファイル検索
du -ah /var/www/style-ai-generator | sort -rh | head -20

# 古いバックアップ削除
find /var/backups/style-ai-generator -mtime +30 -delete

# 古いメディアファイル削除
python manage.py delete_expired_images
```

---

## 緊急時対応

### サービス全停止

```bash
sudo systemctl stop gunicorn celery-worker celery-beat nginx
```

### サービス全起動

```bash
sudo systemctl start postgresql redis-server
sudo systemctl start gunicorn celery-worker celery-beat nginx
```

### ロールバック

```bash
cd /var/www/style-ai-generator
git log --oneline -10  # コミット履歴確認
git checkout <previous_commit_hash>
./scripts/deploy.sh
```

---

## 連絡先

**技術サポート**: tech-support@example.com
**緊急連絡**: emergency@example.com

---

**最終更新日**: 2025-11-01
