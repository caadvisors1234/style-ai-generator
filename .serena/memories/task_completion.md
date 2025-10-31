# タスク完了時に行うこと
1. 関連するユニットテスト・スクリプト (`python manage.py test` など) を実行しログ確認。
2. Celery や WebSocket が絡む変更はローカルでワーカー/Beat を起動して動作確認。
3. ログ (logs/django.log) にエラーがないか確認。
4. 依存関係・設定を変更した場合は docs/ や README を更新し共有。
5. Docker 運用の場合は `docker-compose up` で再ビルド・再起動を確認。