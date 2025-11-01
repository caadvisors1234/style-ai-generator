#!/bin/bash
#
# デプロイスクリプト
# 本番環境へのゼロダウンタイムデプロイ
#
# Usage: ./scripts/deploy.sh [branch_name]
# Default branch: main

set -e

# 設定
BRANCH="${1:-main}"
BACKUP_ON_DEPLOY=${BACKUP_ON_DEPLOY:-true}

# 色付きログ
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
    exit 1
}

log "=== Starting deployment process ==="
log "Branch: $BRANCH"

# 1. デプロイ前確認
log "Step 1: Pre-deployment checks..."

# Git リポジトリ確認
if [ ! -d ".git" ]; then
    error "Not a git repository"
fi

# 未コミットの変更確認
if [ -n "$(git status --porcelain)" ]; then
    warn "Uncommitted changes detected"
    git status --short
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        error "Deployment cancelled"
    fi
fi

# 2. バックアップ
if [ "$BACKUP_ON_DEPLOY" = "true" ]; then
    log "Step 2: Creating backup..."
    if [ -f "scripts/backup.sh" ]; then
        bash scripts/backup.sh || warn "Backup failed"
    else
        warn "Backup script not found"
    fi
else
    log "Step 2: Skipping backup (BACKUP_ON_DEPLOY=false)"
fi

# 3. 最新コード取得
log "Step 3: Fetching latest code..."
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"

COMMIT_HASH=$(git rev-parse --short HEAD)
log "Deployed commit: $COMMIT_HASH"

# 4. 依存パッケージ更新
log "Step 4: Updating dependencies..."
pip install -r requirements.txt --upgrade

# 5. 静的ファイル収集
log "Step 5: Collecting static files..."
python manage.py collectstatic --noinput

# 6. マイグレーション
log "Step 6: Running database migrations..."
python manage.py migrate --noinput

# 7. サービス再起動
log "Step 7: Restarting services..."

# Systemd使用の場合
if command -v systemctl &> /dev/null; then
    log "Restarting gunicorn..."
    sudo systemctl restart gunicorn || warn "Failed to restart gunicorn"

    log "Restarting celery-worker..."
    sudo systemctl restart celery-worker || warn "Failed to restart celery-worker"

    log "Restarting celery-beat..."
    sudo systemctl restart celery-beat || warn "Failed to restart celery-beat"

    log "Reloading nginx..."
    sudo systemctl reload nginx || warn "Failed to reload nginx"

# Docker Compose使用の場合
elif command -v docker-compose &> /dev/null; then
    log "Restarting docker containers..."
    docker-compose restart web celery-worker celery-beat

# 手動再起動の指示
else
    warn "No service manager detected. Please restart services manually:"
    echo "  - Gunicorn"
    echo "  - Celery Worker"
    echo "  - Celery Beat"
    echo "  - Nginx"
fi

# 8. ヘルスチェック
log "Step 8: Health check..."
sleep 5

if command -v curl &> /dev/null; then
    HEALTH_CHECK_URL="${HEALTH_CHECK_URL:-http://localhost:8000/api/v1/health/}"

    log "Checking: $HEALTH_CHECK_URL"

    if curl -f -s "$HEALTH_CHECK_URL" > /dev/null; then
        log "Health check: PASSED ✓"
    else
        error "Health check: FAILED ✗"
    fi
else
    warn "curl not found. Skipping health check."
fi

# 9. デプロイ完了
log "=== Deployment completed successfully ==="
log "Commit: $COMMIT_HASH"
log "Branch: $BRANCH"
log "Time: $(date)"

# 10. デプロイ履歴記録（オプション）
if [ -d "logs" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $COMMIT_HASH - $BRANCH" >> logs/deploy.log
fi
