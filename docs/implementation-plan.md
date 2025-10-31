# 実装計画書

**作成日**: 2025-10-30
**バージョン**: 1.0
**プロジェクト名**: 美容室画像変換システム
**開発期間**: 約4-6週間（想定）

---

## 目次
1. [概要](#概要)
2. [開発環境セットアップ](#phase-0-開発環境セットアップ)
3. [Phase 1: 基盤構築](#phase-1-基盤構築)
4. [Phase 2: 認証・ユーザー管理](#phase-2-認証ユーザー管理)
5. [Phase 3: 画像アップロード機能](#phase-3-画像アップロード機能)
6. [Phase 4: AI画像変換機能](#phase-4-ai画像変換機能)
7. [Phase 5: ギャラリー機能](#phase-5-ギャラリー機能)
8. [Phase 6: 管理機能](#phase-6-管理機能)
9. [Phase 7: フロントエンド実装](#phase-7-フロントエンド実装)
10. [Phase 8: テスト・最適化](#phase-8-テスト最適化)
11. [Phase 9: デプロイ準備](#phase-9-デプロイ準備)

---

## 概要

### 実装方針
- **段階的実装**: 各フェーズごとに機能を完成させ、テストを実施
- **テスト駆動**: 各機能実装後に必ず動作確認を実施
- **ドキュメント準拠**: データベース設計書・API設計書に厳密に従う
- **セキュリティ優先**: 各フェーズでセキュリティ対策を実装

### 技術スタック（再確認）
- Python 3.11+
- Django 5.0+
- PostgreSQL 14+
- Redis 7+
- Celery 5+
- Google Gemini 2.5 Flash Image (Vertex AI)
- Django Channels 4+ (WebSocket)

### 開発順序
```
環境構築 → 基盤 → 認証 → アップロード → AI変換 → ギャラリー → 管理 → フロント → テスト → デプロイ
```

---

## Phase 0: 開発環境セットアップ

**目標**: 開発に必要な環境を整備する
**所要時間**: 1-2日

### タスク

#### プロジェクト構造作成
- [x] Djangoプロジェクト作成（`django-admin startproject config .`）
- [x] 必要なアプリケーション作成
  - [x] `accounts` - ユーザー管理
  - [x] `images` - 画像管理・変換
  - [x] `api` - API エンドポイント
- [x] ディレクトリ構造整備
  ```
  style-ai-generator/
  ├── config/           # プロジェクト設定
  ├── accounts/         # ユーザー管理アプリ
  ├── images/           # 画像管理アプリ
  ├── api/              # APIアプリ
  ├── static/           # 静的ファイル
  ├── media/            # アップロードファイル
  ├── templates/        # テンプレート
  ├── docs/             # ドキュメント（既存）
  ├── requirements.txt  # 依存パッケージ
  └── manage.py
  ```

#### 依存パッケージインストール
- [x] requirements.txt作成
  ```
  Django>=5.0.0
  psycopg2-binary>=2.9.0
  python-dotenv>=1.0.0
  Pillow>=10.0.0
  celery>=5.3.0
  redis>=5.0.0
  channels>=4.0.0
  channels-redis>=4.0.0
  google-cloud-aiplatform>=1.38.0
  google-auth>=2.25.0
  ```
- [x] パッケージインストール（`pip install -r requirements.txt`）

#### データベース設定
- [x] PostgreSQL 14インストール・起動確認（Docker）
- [x] データベース作成（`createdb image_conversion_db`）
- [x] データベースユーザー作成
- [x] `settings.py`にデータベース接続設定

#### Redis設定
- [x] Redis 7インストール・起動確認（Docker）
- [x] Redis接続確認

#### 環境変数設定
- [x] `.env`ファイル作成
  ```
  DEBUG=True
  SECRET_KEY=your-secret-key
  DATABASE_URL=postgresql://user:password@localhost:5432/image_conversion_db
  REDIS_URL=redis://localhost:6379/0
  GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
  GOOGLE_CLOUD_PROJECT=your-project-id
  GOOGLE_CLOUD_LOCATION=us-central1
  ```
- [x] `.gitignore`に`.env`追加

#### Google Cloud設定
- [ ] GCPプロジェクト作成
- [ ] Vertex AI API有効化
- [ ] サービスアカウント作成・キーダウンロード
- [ ] 認証情報テスト

#### バージョン管理
- [ ] Gitリポジトリ初期化（未実施の場合）
- [x] `.gitignore`設定
- [ ] 初期コミット

---

## Phase 1: 基盤構築

**目標**: Djangoプロジェクトの基本設定とデータベースモデルを構築
**所要時間**: 2-3日

### タスク

#### Django基本設定
- [x] `settings.py`基本設定
  - [x] `INSTALLED_APPS`に作成したアプリ追加
  - [x] タイムゾーン設定（`TIME_ZONE = 'Asia/Tokyo'`）
  - [x] 言語設定（`LANGUAGE_CODE = 'ja'`）
  - [x] 静的ファイル設定
  - [x] メディアファイル設定
  - [x] セキュリティ設定（CSRF、XSS対策）

#### セキュリティ設定
- [x] `SECURE_SSL_REDIRECT = True`（本番環境）
- [x] `SESSION_COOKIE_SECURE = True`
- [x] `CSRF_COOKIE_SECURE = True`
- [x] `X_FRAME_OPTIONS = 'DENY'`
- [x] `SECURE_CONTENT_TYPE_NOSNIFF = True`

#### データベースモデル作成

##### accounts アプリ
- [x] `models.py` - UserProfile モデル作成
  ```python
  class UserProfile(models.Model):
      user = models.OneToOneField(User, on_delete=models.CASCADE)
      monthly_limit = models.IntegerField(default=100)
      monthly_used = models.IntegerField(default=0)
      is_deleted = models.BooleanField(default=False)
      created_at = models.DateTimeField(auto_now_add=True)
      updated_at = models.DateTimeField(auto_now=True)
  ```
- [x] UserProfile シグナル設定（User作成時に自動生成）

##### images アプリ
- [x] `models.py` - ImageConversion モデル作成
  ```python
  class ImageConversion(models.Model):
      user = models.ForeignKey(User, on_delete=models.CASCADE)
      original_image_path = models.CharField(max_length=500)
      original_image_name = models.CharField(max_length=255)
      original_image_size = models.IntegerField()
      prompt = models.TextField()
      generation_count = models.IntegerField()
      status = models.CharField(max_length=20)
      processing_time = models.DecimalField(max_digits=10, decimal_places=3)
      error_message = models.TextField(null=True, blank=True)
      is_deleted = models.BooleanField(default=False)
      created_at = models.DateTimeField(auto_now_add=True)
      updated_at = models.DateTimeField(auto_now=True)
  ```
- [x] GeneratedImage モデル作成
  ```python
  class GeneratedImage(models.Model):
      conversion = models.ForeignKey(ImageConversion, on_delete=models.CASCADE)
      image_path = models.CharField(max_length=500)
      image_name = models.CharField(max_length=255)
      image_size = models.IntegerField()
      brightness_adjustment = models.IntegerField(default=0)
      expires_at = models.DateTimeField()
      is_deleted = models.BooleanField(default=False)
      created_at = models.DateTimeField(auto_now_add=True)
      updated_at = models.DateTimeField(auto_now=True)
  ```
- [x] PromptPreset モデル作成（プリセットプロンプト管理）

#### マイグレーション
- [x] 初回マイグレーション作成（`python manage.py makemigrations`）
- [x] マイグレーション適用（`python manage.py migrate`）
- [x] インデックス追加のカスタムマイグレーション作成
- [x] マイグレーション確認（`python manage.py showmigrations`）

#### 管理コマンド作成
- [x] `accounts/management/commands/reset_monthly_usage.py` - 月次リセット
- [x] `images/management/commands/delete_expired_images.py` - 期限切れ画像削除
- [x] コマンド動作確認

---

## Phase 2: 認証・ユーザー管理

**目標**: ログイン・ログアウト機能とユーザー管理機能を実装
**所要時間**: 2-3日

### タスク

#### 認証API実装

##### api/views/auth.py
- [x] ログインAPI実装
  - [x] `POST /api/v1/auth/login/`
  - [x] バリデーション（ユーザー名、パスワード）
  - [x] Django認証処理（`authenticate`, `login`）
  - [x] レスポンス（ユーザー情報、利用状況）
  - [x] エラーハンドリング

- [x] ログアウトAPI実装
  - [x] `POST /api/v1/auth/logout/`
  - [x] セッション破棄（`logout`）
  - [x] レスポンス

- [x] セッション確認API実装
  - [x] `GET /api/v1/auth/me/`
  - [x] `@login_required`デコレータ
  - [x] ユーザー情報・利用状況取得

#### URLルーティング
- [x] `api/urls.py` 作成
- [x] 認証エンドポイント登録
- [x] `config/urls.py` にAPI URLを追加

#### ミドルウェア・デコレータ
- [ ] CSRF保護確認
- [ ] ログイン必須デコレータ設定
- [ ] エラーハンドリングミドルウェア作成

#### 利用状況API実装
- [ ] `GET /api/v1/usage/` - 利用状況取得
- [ ] `GET /api/v1/usage/history/` - 月別履歴取得
- [ ] キャッシュ実装（5分間）

#### テスト
- [ ] ログイン成功・失敗テスト
- [ ] ログアウトテスト
- [ ] セッション確認テスト
- [ ] CSRF保護テスト
- [ ] 利用状況取得テスト

---

## Phase 3: 画像アップロード機能

**目標**: 画像アップロード・検証・削除機能を実装
**所要時間**: 2-3日

### タスク

#### ファイルアップロード処理

##### images/services/upload.py
- [x] アップロード処理サービス作成
  - [x] ファイル検証（形式、サイズ）
  - [x] UUIDベースのファイル名生成
  - [x] ユーザー別ディレクトリ作成
  - [x] ファイル保存処理
  - [x] サムネイル生成（Pillow使用）

#### バリデーション
- [x] ファイル形式チェック（JPEG, PNG, WebP）
- [x] ファイルサイズチェック（最大10MB）
- [x] 同時アップロード数チェック（最大10ファイル）
- [x] MIMEタイプ検証

#### アップロードAPI実装

##### api/views/upload.py
- [x] `POST /api/v1/upload/` - 画像アップロード
  - [x] `@login_required`
  - [x] multipart/form-data処理
  - [x] 複数ファイル対応
  - [x] プレビューURL生成
  - [x] レスポンス（file_path, preview_url等）

- [x] `DELETE /api/v1/upload/delete/` - アップロード削除
  - [x] 権限チェック
  - [x] ファイル削除
  - [x] サムネイルも削除

- [x] `POST /api/v1/upload/validate/` - ファイル検証
  - [x] 事前検証API

#### URLルーティング
- [x] アップロードエンドポイント登録

#### エラーハンドリング
- [x] ファイル形式エラー
- [x] サイズ超過エラー
- [x] 同時アップロード数超過エラー

#### テスト
- [x] 正常アップロードテスト（JPEG, PNG, WebP）
- [x] ファイル形式エラーテスト
- [x] サイズ超過テスト
- [x] 複数ファイルアップロードテスト
- [x] 削除機能テスト

---

## Phase 4: AI画像変換機能

**目標**: Gemini APIを使用した画像変換機能を実装
**所要時間**: 4-5日

### タスク

#### Gemini API統合

##### images/services/gemini.py
- [x] Gemini APIクライアント作成
  - [x] Vertex AI認証設定
  - [x] `generate_content` メソッド実装
  - [x] 画像のBase64エンコード処理
  - [x] リクエスト送信
  - [x] レスポンス処理（画像抽出）
  - [x] エラーハンドリング（レート制限、API エラー）

#### リトライ処理
- [x] Exponential backoff実装
- [x] 最大3回リトライ
- [x] レート制限エラー時の待機処理

#### Celeryタスク設定

##### config/celery.py
- [x] Celeryアプリケーション初期化
- [x] Redis接続設定
- [x] タスクルーティング設定

##### images/tasks.py
- [x] `process_image_conversion` タスク作成
  - [x] 変換ステータス更新（processing）
  - [x] 利用回数チェック
  - [x] 指定枚数分のループ処理
  - [x] 各画像生成（Gemini API呼び出し）
  - [x] 生成画像保存
  - [x] GeneratedImageレコード作成
  - [x] 利用回数更新
  - [x] 処理時間記録
  - [x] ステータス更新（completed/failed）
  - [x] エラー時の処理

#### Celery Beat設定
- [x] `config/settings.py` にBeat設定追加
  - [x] 月次リセット（毎月1日 00:00）
  - [x] 画像自動削除（毎日 02:00）
- [x] タイムゾーン設定（Asia/Tokyo）

#### 変換API実装

##### api/views/convert.py
- [x] `POST /api/v1/convert/` - 変換開始
  - [x] リクエストバリデーション
  - [x] 利用回数チェック
  - [x] ImageConversionレコード作成（status=pending）
  - [x] Celeryタスク投入
  - [x] job_id発行
  - [x] レスポンス（job_id, estimated_time等）

- [x] `GET /api/v1/convert/{job_id}/status/` - 進捗確認
  - [x] ImageConversionステータス取得
  - [x] 進捗情報（current/total）
  - [x] 完了時は生成画像一覧返却

- [x] `POST /api/v1/convert/{job_id}/cancel/` - キャンセル
  - [x] Celeryタスク停止
  - [x] ステータス更新（cancelled）

#### プロンプトAPI実装
- [x] `GET /api/v1/prompts/` - プリセット一覧
  - [x] PromptPresetモデルから取得
  - [x] キャッシュ実装（1時間）

#### プリセットプロンプト登録
- [x] フィクスチャ作成（`images/fixtures/prompts.json`）
  - [x] バックスタイル生成
  - [x] シンプル背景生成
  - [x] 髪の艶感増加
  - [x] 明るく爽やかな雰囲気
  - [x] プロフェッショナルな印象
- [x] `python manage.py loaddata prompts.json`

#### URLルーティング
- [x] 変換エンドポイント登録

#### Gemini 2.5 Flash Image API統合
- [x] `images/services/gemini_image_api.py` 作成
  - [x] Vertex AI経由でGemini 2.5 Flash Image使用
  - [x] google-genaiパッケージ利用
  - [x] Service Account認証
  - [x] 画像生成API実装
  - [x] バリエーション生成機能
  - [x] エラーハンドリング
- [x] パッケージ更新
  - [x] requirements.txtに `google-genai>=0.3.0` 追加
  - [x] Dockerコンテナにインストール
- [x] Celeryタスク更新
  - [x] `images/tasks.py` を新しいAPIサービスで書き直し
  - [x] 画像保存処理の最適化

#### テスト
- [x] Gemini API接続テスト
- [x] 画像変換テスト（1枚）
- [x] 複数枚生成テスト（3枚、5枚）
- [ ] 利用回数超過テスト
- [ ] エラーハンドリングテスト（API エラー）
- [ ] リトライ処理テスト
- [ ] キャンセル機能テスト

---

## Phase 5: ギャラリー機能

**目標**: 生成画像の閲覧・管理機能を実装
**所要時間**: 3-4日

### タスク

#### ギャラリーAPI実装

##### api/views/gallery.py
- [x] `GET /api/v1/gallery/` - 一覧取得
  - [x] ユーザーフィルタリング
  - [x] ページネーション実装
  - [x] ソート機能（created_at）
  - [x] 検索機能（プロンプト部分一致）
  - [x] select_related/prefetch_related最適化
  - [x] レスポンス（サムネイル含む）

- [x] `GET /api/v1/gallery/{conversion_id}/` - 詳細取得
  - [x] 権限チェック（自分のデータのみ）
  - [x] Before/After画像情報
  - [x] 生成画像一覧

- [x] `DELETE /api/v1/gallery/{conversion_id}/` - 削除
  - [x] 権限チェック
  - [x] 論理削除（is_deleted=True）
  - [x] 関連画像も削除

#### 画像詳細API実装
- [x] `GET /api/v1/gallery/images/{image_id}/` - 画像詳細
  - [x] 権限チェック
  - [x] 画像情報取得

- [x] `DELETE /api/v1/gallery/images/{image_id}/` - 画像削除
  - [x] 権限チェック
  - [x] 論理削除

#### 輝度調整API実装

##### images/services/brightness.py
- [x] 輝度調整処理サービス作成
  - [x] Pillow使用（ImageEnhance.Brightness）
  - [x] 輝度係数計算（-50〜+50 → 0.5〜1.5）
  - [x] 調整済み画像保存

##### api/views/gallery.py
- [x] `PATCH /api/v1/gallery/images/{image_id}/brightness/`
  - [x] バリデーション（-50〜+50）
  - [x] 輝度調整処理呼び出し
  - [x] brightness_adjustment更新
  - [x] 調整済み画像URL返却

#### ダウンロードAPI実装
- [x] `GET /api/v1/gallery/images/{image_id}/download/`
  - [x] 権限チェック
  - [x] FileResponse返却
  - [x] Content-Disposition設定
  - [x] ファイル名生成（generated_YYYYMMDD_HHMMSS.ext）

#### URLルーティング
- [x] ギャラリーエンドポイント登録（7エンドポイント）

#### テスト
- [x] 一覧取得テスト
- [x] 詳細取得テスト
- [x] 権限チェックテスト

---

## Phase 6: 管理機能

**目標**: Django Admin を使用した管理機能を実装
**所要時間**: 2日

### タスク

#### Admin設定

##### accounts/admin.py
- [x] UserProfileAdmin作成
  - [x] list_display設定（username, monthly_limit, monthly_used, remaining）
  - [x] list_filter設定（is_deleted, created_at）
  - [x] search_fields設定（user__username）
  - [x] readonly_fields設定（created_at, updated_at）
  - [x] fieldsets設定
  - [x] 残り回数表示メソッド追加（色付き表示）
  - [x] ユーザーモデルにインライン編集追加（UserProfileInline）

##### images/admin.py
- [x] ImageConversionAdmin作成
  - [x] list_display（user, prompt抜粋, status, generation_count, created_at）
  - [x] list_filter（status, created_at）
  - [x] search_fields（user__username, prompt）
  - [x] readonly_fields（processing_time, created_at, updated_at）
  - [x] 生成画像インライン表示（GeneratedImageInline）
  - [x] 元画像プレビュー表示
  - [x] ステータス色付き表示

- [x] GeneratedImageAdmin作成
  - [x] list_display（conversion, image_name, created_at, expires_at）
  - [x] list_filter（is_deleted, created_at）
  - [x] 画像プレビュー表示（サムネイル＋詳細）

- [x] PromptPresetAdmin作成
  - [x] list_display（name, category）
  - [x] list_filter（category）
  - [x] list_editable（is_active, display_order）

#### スーパーユーザー作成
- [x] `python manage.py createsuperuser`（admin/admin123）
- [x] 管理画面アクセス確認

#### カスタムアクション
- [x] UserProfile一括リセットアクション
- [x] 論理削除/有効化アクション（UserProfile, ImageConversion, GeneratedImage）
- [x] 有効期限延長アクション（GeneratedImage）
- [x] プリセット有効化/無効化アクション

#### 管理画面カスタマイズ
- [x] サイトタイトル変更（美容室画像変換システム 管理画面）
- [x] ヘッダー変更
- [x] 日本語化確認

#### テスト
- [x] 管理画面アクセステスト

---

## Phase 7: フロントエンド実装

**目標**: ユーザー向けのWebインターフェースを実装
**所要時間**: 5-7日

### タスク

#### ベーステンプレート作成

##### templates/base.html
- [ ] HTML5基本構造
- [ ] CSSフレームワーク導入（Bootstrap 5推奨）
- [ ] 共通ヘッダー（ロゴ、ナビゲーション、ログアウトボタン）
- [ ] 共通フッター
- [ ] 利用状況表示エリア
- [ ] トースト通知エリア
- [ ] CSRFトークン自動取得スクリプト

#### ログイン画面

##### templates/auth/login.html
- [ ] ログインフォーム
  - [ ] ユーザー名入力
  - [ ] パスワード入力
  - [ ] ログインボタン
  - [ ] エラーメッセージ表示エリア
- [ ] フォーム送信処理（JavaScript）
- [ ] API呼び出し（`POST /api/v1/auth/login/`）
- [ ] 成功時リダイレクト（メイン画面）
- [ ] エラー表示

#### メイン画面（アップロード・変換）

##### templates/main.html
- [ ] ドラッグ&ドロップエリア
  - [ ] ドロップゾーン
  - [ ] ファイル選択ボタン
  - [ ] ドロップ時の視覚的フィードバック
- [ ] アップロード済み画像プレビュー
  - [ ] サムネイル表示
  - [ ] ファイル名表示
  - [ ] 削除ボタン
- [ ] プロンプト選択エリア
  - [ ] プリセットボタン（5種類）
  - [ ] カスタム入力テキストエリア
  - [ ] 選択中プロンプトハイライト
- [ ] 生成枚数選択
  - [ ] ドロップダウン（1-5枚）
- [ ] 変換開始ボタン
- [ ] 利用状況表示（ヘッダー）

##### static/js/main.js
- [ ] ドラッグ&ドロップ処理
- [ ] ファイル選択処理
- [ ] アップロードAPI呼び出し
- [ ] プレビュー表示
- [ ] プロンプト選択処理
- [ ] 変換開始処理
- [ ] バリデーション
- [ ] エラーハンドリング

#### 処理中画面（進捗表示）

##### templates/processing.html
- [ ] ローディングアニメーション（スピナー）
- [ ] 進捗メッセージ表示
- [ ] 進捗インジケーター（X/Y枚目）
- [ ] プログレスバー
- [ ] キャンセルボタン

##### WebSocket実装（オプション: ポーリングでも可）

###### config/asgi.py
- [ ] Django Channels設定
- [ ] WebSocketルーティング

###### images/consumers.py
- [ ] ConversionConsumer作成
  - [ ] WebSocket接続処理
  - [ ] 進捗更新メッセージ送信
  - [ ] 完了通知
  - [ ] エラー通知

##### static/js/progress.js
- [ ] WebSocket接続（またはポーリング）
- [ ] 進捗更新処理
- [ ] 完了時リダイレクト（ギャラリー）
- [ ] エラー表示
- [ ] キャンセル処理

#### ギャラリー画面

##### templates/gallery.html
- [ ] 画像グリッド表示（3-4列）
- [ ] サムネイル表示
- [ ] 生成日時表示
- [ ] プロンプト表示（省略）
- [ ] フィルター・ソート機能
  - [ ] ソートドロップダウン
  - [ ] 検索入力
- [ ] ページネーション
- [ ] 詳細表示モーダルトリガー

##### static/js/gallery.js
- [ ] ギャラリー一覧取得
- [ ] グリッド表示処理
- [ ] フィルター処理
- [ ] ソート処理
- [ ] ページネーション処理
- [ ] モーダル表示処理

#### 画像詳細モーダル

##### templates/components/image_detail_modal.html
- [ ] Before/After比較表示
  - [ ] 左: 元画像
  - [ ] 右: 変換後画像
- [ ] 生成情報表示
  - [ ] 生成日時
  - [ ] プロンプト
  - [ ] 生成枚数（スライダー）
- [ ] 輝度調整スライダー
  - [ ] 範囲: -50〜+50
  - [ ] リアルタイムプレビュー
  - [ ] リセットボタン
  - [ ] 適用ボタン
- [ ] ダウンロードボタン
- [ ] 削除ボタン
- [ ] 閉じるボタン

##### static/js/image_detail.js
- [ ] 詳細取得API呼び出し
- [ ] Before/After表示
- [ ] 輝度調整処理（Canvas API）
- [ ] 輝度適用API呼び出し
- [ ] ダウンロード処理
- [ ] 削除処理
- [ ] 確認ダイアログ

#### 共通JavaScript

##### static/js/api-client.js
- [ ] APIClientクラス作成（API設計書参照）
- [ ] CSRFトークン取得
- [ ] エラーハンドリング
- [ ] リクエストラッパー

##### static/js/notifications.js
- [ ] トースト通知関数
- [ ] 成功通知（緑）
- [ ] エラー通知（赤）
- [ ] 警告通知（黄）

#### CSS

##### static/css/styles.css
- [ ] 共通スタイル
- [ ] ドラッグ&ドロップエリアスタイル
- [ ] プロンプトボタンスタイル
- [ ] ギャラリーグリッドスタイル
- [ ] モーダルスタイル
- [ ] レスポンシブ対応

#### テスト
- [ ] ログイン画面動作確認
- [ ] アップロード機能確認
- [ ] プロンプト選択確認
- [ ] 変換開始確認
- [ ] 進捗表示確認
- [ ] ギャラリー表示確認
- [ ] 詳細モーダル確認
- [ ] 輝度調整確認
- [ ] ダウンロード確認
- [ ] 削除確認
- [ ] レスポンシブ確認

---

## Phase 8: テスト・最適化

**目標**: システム全体のテストとパフォーマンス最適化
**所要時間**: 3-4日

### タスク

#### ユニットテスト作成

##### accounts/tests.py
- [ ] UserProfileモデルテスト
- [ ] 認証APIテスト
- [ ] 利用状況APIテスト
- [ ] 権限チェックテスト

##### images/tests.py
- [ ] ImageConversionモデルテスト
- [ ] GeneratedImageモデルテスト
- [ ] アップロードAPIテスト
- [ ] 変換APIテスト
- [ ] ギャラリーAPIテスト
- [ ] Gemini APIモックテスト

##### 管理コマンドテスト
- [ ] 月次リセットテスト
- [ ] 画像自動削除テスト

#### 統合テスト
- [ ] エンドツーエンドテスト（ログイン→アップロード→変換→ギャラリー）
- [ ] 複数ユーザー同時処理テスト
- [ ] 利用制限テスト
- [ ] エラーリカバリーテスト

#### パフォーマンステスト
- [ ] クエリパフォーマンス確認（EXPLAIN ANALYZE）
- [ ] N+1問題チェック
- [ ] ページネーション負荷テスト
- [ ] 画像アップロード負荷テスト
- [ ] Celeryタスク処理速度確認

#### パフォーマンス最適化
- [ ] データベースクエリ最適化
  - [ ] select_related/prefetch_related追加
  - [ ] インデックス確認
  - [ ] 不要なクエリ削減
- [ ] キャッシュ実装
  - [ ] プロンプト一覧キャッシュ
  - [ ] 利用状況キャッシュ
  - [ ] Redis接続確認
- [ ] 画像最適化
  - [ ] サムネイル品質調整
  - [ ] WebP形式対応検討

#### セキュリティテスト
- [ ] CSRF保護確認
- [ ] SQLインジェクション対策確認
- [ ] XSS対策確認
- [ ] ファイルアップロード脆弱性確認
- [ ] 権限チェック漏れ確認
- [ ] セッション管理確認

#### 負荷テスト
- [ ] 同時接続数テスト（10ユーザー）
- [ ] 画像変換キュー処理テスト
- [ ] データベース接続プール確認

#### ログ・監視設定
- [ ] ログ設定
  - [ ] ERROR以上はファイル出力
  - [ ] INFO以上はコンソール出力
  - [ ] ログローテーション設定
- [ ] エラー通知設定（オプション）

---

## Phase 9: デプロイ準備

**目標**: 本番環境へのデプロイ準備
**所要時間**: 2-3日

### タスク

#### Docker化

##### Dockerfile
- [ ] Dockerfile作成
  - [ ] Python 3.11ベース
  - [ ] 依存パッケージインストール
  - [ ] アプリケーションコピー
  - [ ] 静的ファイル収集
  - [ ] Gunicorn設定

##### docker-compose.yml
- [ ] docker-compose.yml作成
  - [ ] Webサービス（Django + Gunicorn）
  - [ ] PostgreSQLサービス
  - [ ] Redisサービス
  - [ ] Celeryワーカーサービス
  - [ ] Celery Beatサービス
  - [ ] ボリューム設定（media, static）
  - [ ] ネットワーク設定

#### 本番設定

##### config/settings/production.py
- [ ] 本番用設定ファイル作成
  - [ ] DEBUG = False
  - [ ] ALLOWED_HOSTS設定
  - [ ] データベース設定（環境変数）
  - [ ] 静的ファイル設定
  - [ ] メディアファイル設定
  - [ ] セキュリティ設定
  - [ ] ログ設定

#### Webサーバー設定

##### Nginx設定
- [ ] nginx.conf作成
  - [ ] リバースプロキシ設定
  - [ ] 静的ファイル配信
  - [ ] メディアファイル配信
  - [ ] SSL/TLS設定
  - [ ] gzip圧縮
  - [ ] セキュリティヘッダー

##### Gunicorn設定
- [ ] gunicorn.conf.py作成
  - [ ] ワーカー数設定
  - [ ] タイムアウト設定
  - [ ] ログ設定

#### SSL/TLS証明書
- [ ] Let's Encrypt証明書取得
- [ ] 自動更新設定

#### 環境変数設定
- [ ] 本番用`.env`作成
  - [ ] SECRET_KEY（ランダム生成）
  - [ ] DATABASE_URL
  - [ ] REDIS_URL
  - [ ] GOOGLE_APPLICATION_CREDENTIALS
  - [ ] ALLOWED_HOSTS

#### デプロイスクリプト

##### scripts/deploy.sh
- [ ] デプロイスクリプト作成
  - [ ] Gitプル
  - [ ] 依存パッケージ更新
  - [ ] マイグレーション実行
  - [ ] 静的ファイル収集
  - [ ] サービス再起動

#### バックアップ設定

##### scripts/backup.sh
- [ ] データベースバックアップスクリプト
- [ ] メディアファイルバックアップスクリプト
- [ ] Cronジョブ設定（日次）

#### 監視設定
- [ ] ヘルスチェックエンドポイント作成
- [ ] アップタイム監視設定（オプション）
- [ ] エラーログ監視（オプション）

#### ドキュメント作成

##### docs/deployment.md
- [ ] デプロイ手順書作成
- [ ] 環境変数一覧
- [ ] トラブルシューティング

##### docs/operations.md
- [ ] 運用手順書作成
  - [ ] バックアップ・リストア手順
  - [ ] ユーザー管理手順
  - [ ] 月次メンテナンス手順
  - [ ] ログ確認手順

##### README.md
- [ ] プロジェクト概要
- [ ] セットアップ手順
- [ ] 開発手順
- [ ] テスト実行方法

#### 最終確認
- [ ] 全機能動作確認
- [ ] パフォーマンス確認
- [ ] セキュリティ確認
- [ ] バックアップ・リストア確認
- [ ] ログ確認
- [ ] 監視確認

---

## 進捗管理

### 全体進捗

- [x] Phase 0: 開発環境セットアップ（100%）
- [x] Phase 1: 基盤構築（100%）
- [x] Phase 2: 認証・ユーザー管理（80% - API実装完了、テスト未実施）
- [x] Phase 3: 画像アップロード機能（100% - 実装・テスト完了）
- [x] Phase 4: AI画像変換機能（90% - コア実装完了、テスト未実施）
- [x] Phase 5: ギャラリー機能（100% - 実装・テスト完了）
- [ ] Phase 6: 管理機能（0%）
- [ ] Phase 7: フロントエンド実装（0%）
- [ ] Phase 8: テスト・最適化（0%）
- [ ] Phase 9: デプロイ準備（0%）

### 完了基準

各フェーズの完了基準：
1. 全タスクのチェックボックスが完了
2. 該当フェーズのテストが全て合格
3. コードレビュー完了（セルフレビュー含む）
4. ドキュメント更新完了

---

## リスク管理

### 想定されるリスクと対策

| リスク | 影響度 | 対策 |
|--------|--------|------|
| Gemini API制限 | 高 | リトライ処理、エラーハンドリング強化 |
| パフォーマンス問題 | 中 | 早期テスト、キャッシュ活用 |
| セキュリティ脆弱性 | 高 | セキュリティチェック徹底 |
| デプロイトラブル | 中 | 段階的デプロイ、ロールバック準備 |
| スケジュール遅延 | 中 | バッファ確保、優先順位明確化 |

---

## 次のステップ

実装計画書が承認されたら、以下の順序で進めます：

1. **Phase 0開始**: 開発環境セットアップ
2. **定期報告**: 各フェーズ完了時に進捗報告
3. **問題発生時**: 即座に報告し、対策を協議
4. **フェーズ完了時**: レビュー実施、次フェーズへ

---

**文書履歴**:
- 2025-10-30: 初版作成
