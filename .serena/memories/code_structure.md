# ディレクトリ構成概要
- `config/`: Django プロジェクト設定、Celery/ASGI 初期化、URL ルーティング。
- `accounts/`: UserProfile 拡張モデル、管理画面、月次リセットタスクと管理コマンド。
- `images/`: 画像変換ドメイン。ImageConversion/GeneratedImage/PromptPreset モデル、Gemini 連携サービス、Brighteness 調整、Celery タスク、WebSocket コンシューマ、管理コマンド、初期プリセット fixture。
- `api/`: REST API レイヤー。認証・アップロード・変換・ギャラリー・プロンプトエンドポイント群とURL設定。
- `static/`, `media/`, `staticfiles/`, `sample/`: 静的/メディア/サンプル資材。
- `docs/`: 要件・API・DB・実装計画・セットアップ・Gemini仕様ドキュメント。
- ルート: `docker-compose.yml`, `Dockerfile`, `requirements.txt`, Gemini 接続テストスクリプトなど。