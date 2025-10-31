#!/usr/bin/env bash
#
# 開発環境向けユーティリティスクリプト
# Django 開発サーバー・Celery ワーカー・Celery Beat を同時に起動し、
# WebSocket (Channels) を含むバックグラウンド処理を一括で確認できるようにする。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-config.settings}

cd "$ROOT_DIR"

cleanup() {
  trap - SIGINT SIGTERM EXIT
  if [ -n "${RUNSERVER_PID:-}" ] && ps -p "$RUNSERVER_PID" > /dev/null 2>&1; then
    kill "$RUNSERVER_PID"
  fi
  if [ -n "${CELERY_WORKER_PID:-}" ] && ps -p "$CELERY_WORKER_PID" > /dev/null 2>&1; then
    kill "$CELERY_WORKER_PID"
  fi
  if [ -n "${CELERY_BEAT_PID:-}" ] && ps -p "$CELERY_BEAT_PID" > /dev/null 2>&1; then
    kill "$CELERY_BEAT_PID"
  fi
}

trap cleanup SIGINT SIGTERM EXIT

python manage.py runserver 0.0.0.0:8000 &
RUNSERVER_PID=$!

celery -A config worker -l info &
CELERY_WORKER_PID=$!

celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler &
CELERY_BEAT_PID=$!

wait
