#!/bin/bash
#
# バックアップスクリプト
# データベースとメディアファイルを定期的にバックアップ
#
# Usage: ./scripts/backup.sh
# Cron: 0 2 * * * /path/to/scripts/backup.sh

set -e

# 設定
BACKUP_DIR="${BACKUP_DIR:-/var/backups/style-ai-generator}"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=${RETENTION_DAYS:-30}

# ログ設定
LOG_FILE="${BACKUP_DIR}/backup.log"

# ログ出力関数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Backup started ==="

# バックアップディレクトリ作成
mkdir -p "$BACKUP_DIR"

# 環境変数読み込み
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# 1. データベースバックアップ
log "Backing up database..."
if [ -n "$DATABASE_URL" ]; then
    pg_dump "$DATABASE_URL" > "$BACKUP_DIR/db_$DATE.sql"
    gzip "$BACKUP_DIR/db_$DATE.sql"
    log "Database backup completed: db_$DATE.sql.gz"
else
    log "ERROR: DATABASE_URL not set"
    exit 1
fi

# 2. メディアファイルバックアップ
log "Backing up media files..."
if [ -d "media" ]; then
    tar -czf "$BACKUP_DIR/media_$DATE.tar.gz" media/
    log "Media backup completed: media_$DATE.tar.gz"
else
    log "WARNING: media directory not found"
fi

# 3. 設定ファイルバックアップ（オプション）
log "Backing up configuration files..."
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    config/ gunicorn.conf.py nginx/

log "Configuration backup completed: config_$DATE.tar.gz"

# 4. 古いバックアップ削除
log "Cleaning up old backups (older than ${RETENTION_DAYS} days)..."
find "$BACKUP_DIR" -type f -name "db_*.sql.gz" -mtime +${RETENTION_DAYS} -delete
find "$BACKUP_DIR" -type f -name "media_*.tar.gz" -mtime +${RETENTION_DAYS} -delete
find "$BACKUP_DIR" -type f -name "config_*.tar.gz" -mtime +${RETENTION_DAYS} -delete

# 5. バックアップサイズ確認
log "Current backup size:"
du -sh "$BACKUP_DIR"

# 6. バックアップファイル一覧
log "Recent backups:"
ls -lh "$BACKUP_DIR" | tail -10

log "=== Backup completed successfully ===" log ""
