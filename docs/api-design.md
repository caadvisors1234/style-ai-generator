# API設計書

**作成日**: 2025-10-30
**バージョン**: 1.0
**プロジェクト名**: 美容室画像変換システム
**APIバージョン**: v1

---

## 目次
1. [概要](#概要)
2. [認証・認可](#認証認可)
3. [共通仕様](#共通仕様)
4. [エンドポイント一覧](#エンドポイント一覧)
5. [詳細API仕様](#詳細api仕様)
6. [エラーハンドリング](#エラーハンドリング)
7. [レート制限](#レート制限)
8. [WebSocket仕様](#websocket仕様)
9. [ベストプラクティス](#ベストプラクティス)

---

## 概要

### API設計方針
- **RESTful API**: リソース指向のURL設計
- **JSON形式**: リクエスト・レスポンスは全てJSON
- **ステートレス**: セッションベース認証（Django標準）
- **HTTPS必須**: 全ての通信を暗号化
- **バージョニング**: URLパス方式 (`/api/v1/`)

### 技術スタック
- **フレームワーク**: Django 5.0+ (標準Views使用)
- **認証**: Django標準セッション認証 + CSRF保護
- **リアルタイム通信**: Django Channels (WebSocket)
- **非同期処理**: Celery + Redis

### ベースURL
```
開発環境: https://localhost:8000/api/v1/
本番環境: https://your-domain.com/api/v1/
```

---

## 認証・認可

### 認証方式

本システムはDjango標準のセッションベース認証を使用します。

#### ログイン
```http
POST /api/v1/auth/login/
Content-Type: application/json

{
  "username": "user123",
  "password": "secure_password"
}
```

**成功レスポンス (200 OK)**:
```json
{
  "success": true,
  "user": {
    "id": 1,
    "username": "user123",
    "monthly_limit": 100,
    "monthly_used": 25,
    "remaining": 75
  },
  "message": "ログインに成功しました"
}
```

**失敗レスポンス (401 Unauthorized)**:
```json
{
  "success": false,
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "ユーザー名またはパスワードが正しくありません"
  }
}
```

#### ログアウト
```http
POST /api/v1/auth/logout/
```

**成功レスポンス (200 OK)**:
```json
{
  "success": true,
  "message": "ログアウトしました"
}
```

#### セッション確認
```http
GET /api/v1/auth/me/
```

**成功レスポンス (200 OK)**:
```json
{
  "user": {
    "id": 1,
    "username": "user123",
    "monthly_limit": 100,
    "monthly_used": 25,
    "remaining": 75,
    "last_login": "2025-10-30T10:30:00+09:00"
  }
}
```

### CSRF保護

全てのPOST/PUT/PATCH/DELETEリクエストにはCSRFトークンが必要です。

```javascript
// Cookieからトークンを取得
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
}

// リクエストヘッダーに含める
fetch('/api/v1/upload/', {
  method: 'POST',
  headers: {
    'X-CSRFToken': getCookie('csrftoken'),
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(data)
});
```

---

## 共通仕様

### HTTPヘッダー

#### リクエストヘッダー
```http
Content-Type: application/json
X-CSRFToken: <csrf_token>
Accept: application/json
```

#### レスポンスヘッダー
```http
Content-Type: application/json; charset=utf-8
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
```

### 共通レスポンス形式

#### 成功レスポンス
```json
{
  "success": true,
  "data": { ... },
  "message": "処理が完了しました"
}
```

#### エラーレスポンス
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "エラーメッセージ",
    "details": { ... }
  }
}
```

### ページネーション

大量データのリストAPIではページネーションを実装。

```http
GET /api/v1/gallery/?page=2&page_size=20
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "count": 150,
    "next": "/api/v1/gallery/?page=3&page_size=20",
    "previous": "/api/v1/gallery/?page=1&page_size=20",
    "results": [ ... ]
  }
}
```

### 日時フォーマット

ISO 8601形式を使用（タイムゾーン付き）

```json
{
  "created_at": "2025-10-30T10:30:00+09:00"
}
```

---

## エンドポイント一覧

### 認証関連

| メソッド | エンドポイント | 説明 | 認証 |
|---------|--------------|------|------|
| POST | `/api/v1/auth/login/` | ログイン | 不要 |
| POST | `/api/v1/auth/logout/` | ログアウト | 必要 |
| GET | `/api/v1/auth/me/` | セッション確認 | 必要 |

### 画像アップロード関連

| メソッド | エンドポイント | 説明 | 認証 |
|---------|--------------|------|------|
| POST | `/api/v1/upload/` | 画像アップロード | 必要 |
| DELETE | `/api/v1/upload/{upload_id}/` | アップロード削除 | 必要 |
| GET | `/api/v1/upload/validate/` | ファイル検証 | 必要 |

### 画像変換関連

| メソッド | エンドポイント | 説明 | 認証 |
|---------|--------------|------|------|
| POST | `/api/v1/convert/` | 変換開始 | 必要 |
| GET | `/api/v1/convert/{job_id}/status/` | 進捗確認 | 必要 |
| POST | `/api/v1/convert/{job_id}/cancel/` | 変換キャンセル | 必要 |
| GET | `/api/v1/prompts/` | プロンプト一覧取得 | 必要 |

### ギャラリー関連

| メソッド | エンドポイント | 説明 | 認証 |
|---------|--------------|------|------|
| GET | `/api/v1/gallery/` | ギャラリー一覧 | 必要 |
| GET | `/api/v1/gallery/{conversion_id}/` | 変換詳細取得 | 必要 |
| DELETE | `/api/v1/gallery/{conversion_id}/` | 変換削除 | 必要 |
| GET | `/api/v1/gallery/images/{image_id}/` | 画像詳細 | 必要 |
| DELETE | `/api/v1/gallery/images/{image_id}/` | 画像削除 | 必要 |
| PATCH | `/api/v1/gallery/images/{image_id}/brightness/` | 輝度調整 | 必要 |
| GET | `/api/v1/gallery/images/{image_id}/download/` | 画像ダウンロード | 必要 |

### 利用状況関連

| メソッド | エンドポイント | 説明 | 認証 |
|---------|--------------|------|------|
| GET | `/api/v1/usage/` | 利用状況取得 | 必要 |
| GET | `/api/v1/usage/history/` | 利用履歴取得 | 必要 |

---

## 詳細API仕様

### 1. 画像アップロード

#### POST /api/v1/upload/

**説明**: 画像ファイルをアップロードして一時保存

**リクエスト**:
```http
POST /api/v1/upload/
Content-Type: multipart/form-data

files: [File, File, ...]  # 最大10ファイル
```

**成功レスポンス (201 Created)**:
```json
{
  "success": true,
  "data": {
    "uploads": [
      {
        "upload_id": "uuid-1234-5678",
        "filename": "sample.jpg",
        "size": 2048576,
        "preview_url": "/media/temp/preview_uuid.jpg",
        "mime_type": "image/jpeg"
      }
    ]
  },
  "message": "1件の画像をアップロードしました"
}
```

**エラーレスポンス (400 Bad Request)**:
```json
{
  "success": false,
  "error": {
    "code": "INVALID_FILE",
    "message": "対応していないファイル形式です",
    "details": {
      "allowed_types": ["image/jpeg", "image/png", "image/webp"],
      "max_size": 10485760
    }
  }
}
```

**バリデーション**:
- ファイル形式: JPEG, PNG, WebP
- 最大サイズ: 10MB/ファイル
- 同時アップロード: 最大10ファイル

---

#### DELETE /api/v1/upload/{upload_id}/

**説明**: アップロード済み画像を削除

**リクエスト**:
```http
DELETE /api/v1/upload/uuid-1234-5678/
```

**成功レスポンス (200 OK)**:
```json
{
  "success": true,
  "message": "画像を削除しました"
}
```

---

### 2. 画像変換

#### POST /api/v1/convert/

**説明**: 画像変換処理を開始

**リクエスト**:
```http
POST /api/v1/convert/
Content-Type: application/json

{
  "upload_id": "uuid-1234-5678",
  "prompt": "背景を白い無地の背景に変更してください",
  "generation_count": 3
}
```

**リクエストボディ**:
| フィールド | 型 | 必須 | 説明 |
|----------|-----|-----|------|
| upload_id | string | ○ | アップロードID |
| prompt | string | ○ | 変換プロンプト (最大500文字) |
| generation_count | integer | ○ | 生成枚数 (1-5) |

**成功レスポンス (202 Accepted)**:
```json
{
  "success": true,
  "data": {
    "job_id": "job_abc123",
    "conversion_id": 42,
    "status": "pending",
    "estimated_time": 30,
    "queue_position": 2
  },
  "message": "変換処理を開始しました"
}
```

**エラーレスポンス (403 Forbidden)**:
```json
{
  "success": false,
  "error": {
    "code": "QUOTA_EXCEEDED",
    "message": "今月の利用可能回数を超過しています",
    "details": {
      "monthly_limit": 100,
      "monthly_used": 98,
      "remaining": 2,
      "requested": 3
    }
  }
}
```

**バリデーション**:
- 利用回数チェック: `remaining >= generation_count`
- プロンプト長: 最大500文字
- 生成枚数: 1〜5枚

---

#### GET /api/v1/convert/{job_id}/status/

**説明**: 変換処理の進捗状況を取得

**リクエスト**:
```http
GET /api/v1/convert/job_abc123/status/
```

**成功レスポンス (200 OK)**:

**処理中**:
```json
{
  "success": true,
  "data": {
    "job_id": "job_abc123",
    "status": "processing",
    "progress": {
      "current": 2,
      "total": 5,
      "percentage": 40
    },
    "message": "画像 2/5 枚目を生成中...",
    "started_at": "2025-10-30T10:30:00+09:00"
  }
}
```

**完了**:
```json
{
  "success": true,
  "data": {
    "job_id": "job_abc123",
    "status": "completed",
    "conversion_id": 42,
    "generated_images": [
      {
        "image_id": 101,
        "image_url": "/media/generated/user_1/image_101.png",
        "thumbnail_url": "/media/generated/user_1/thumb_101.png"
      },
      {
        "image_id": 102,
        "image_url": "/media/generated/user_1/image_102.png",
        "thumbnail_url": "/media/generated/user_1/thumb_102.png"
      }
    ],
    "processing_time": 28.5,
    "completed_at": "2025-10-30T10:30:28+09:00"
  }
}
```

**失敗**:
```json
{
  "success": false,
  "data": {
    "job_id": "job_abc123",
    "status": "failed",
    "error_message": "API rate limit exceeded. Please try again later.",
    "failed_at": "2025-10-30T10:30:15+09:00"
  }
}
```

**ステータス値**:
- `pending`: 処理待ち
- `processing`: 処理中
- `completed`: 完了
- `failed`: 失敗
- `cancelled`: キャンセル済み（ユーザーがキャンセルした変換。ギャラリーからは除外される）

---

#### POST /api/v1/convert/{job_id}/cancel/

**説明**: 処理中の変換をキャンセル

**リクエスト**:
```http
POST /api/v1/convert/job_abc123/cancel/
```

**成功レスポンス (200 OK)**:
```json
{
  "success": true,
  "message": "変換処理をキャンセルしました"
}
```

---

#### GET /api/v1/prompts/

**説明**: プリセットプロンプト一覧を取得

**リクエスト**:
```http
GET /api/v1/prompts/
```

**成功レスポンス (200 OK)**:
```json
{
  "success": true,
  "data": {
    "prompts": [
      {
        "id": 1,
        "name": "バックスタイル生成",
        "prompt": "正面写真から背面のヘアスタイルを生成してください",
        "category": "style"
      },
      {
        "id": 2,
        "name": "シンプル背景生成",
        "prompt": "背景を白い無地の背景に変更してください",
        "category": "background"
      },
      {
        "id": 3,
        "name": "髪の艶感増加",
        "prompt": "髪に自然な艶と輝きを追加し、健康的な印象を強調してください",
        "category": "enhancement"
      },
      {
        "id": 4,
        "name": "明るく爽やかな雰囲気",
        "prompt": "全体の色調を明るくし、爽やかで清潔感のある雰囲気に仕上げてください",
        "category": "tone"
      },
      {
        "id": 5,
        "name": "プロフェッショナルな印象",
        "prompt": "プロフェッショナルで洗練された印象の画像に変換してください",
        "category": "professional"
      }
    ]
  }
}
```

---

### 3. ギャラリー

#### GET /api/v1/gallery/

**説明**: ユーザーの変換履歴一覧を取得

**リクエスト**:
```http
GET /api/v1/gallery/?page=1&page_size=20&sort=-created_at&search=髪
```

**クエリパラメータ**:
| パラメータ | 型 | 必須 | 説明 |
|----------|-----|-----|------|
| page | integer | × | ページ番号 (デフォルト: 1) |
| page_size | integer | × | 1ページあたりの件数 (デフォルト: 20, 最大: 100) |
| sort | string | × | ソート順 (`created_at`, `-created_at`) |
| search | string | × | プロンプト部分一致検索 |

**成功レスポンス (200 OK)**:
```json
{
  "status": "success",
  "conversions": [
    {
      "id": 42,
      "original_image_url": "/media/uploads/user_1/original.jpg",
      "original_image_name": "original.jpg",
      "prompt": "背景を白に変更",
      "generation_count": 3,
      "aspect_ratio": "4:3",
      "status": "completed",
      "processing_time": 28.5,
      "created_at": "2025-10-30T10:30:00+09:00",
      "generated_images": [
        {
          "id": 101,
          "image_url": "/media/generated/user_1/image_101.png",
          "thumbnail_url": "/media/generated/user_1/image_101.png",
          "brightness_adjustment": 0,
          "expires_at": "2025-11-29T10:30:00+09:00",
          "created_at": "2025-10-30T10:30:10+09:00"
        },
        {
          "id": 102,
          "image_url": "/media/generated/user_1/image_102.png",
          "thumbnail_url": "/media/generated/user_1/image_102.png",
          "brightness_adjustment": 0,
          "expires_at": "2025-11-29T10:30:00+09:00",
          "created_at": "2025-10-30T10:30:18+09:00"
        },
        {
          "id": 103,
          "image_url": "/media/generated/user_1/image_103.png",
          "thumbnail_url": "/media/generated/user_1/image_103.png",
          "brightness_adjustment": 0,
          "expires_at": "2025-11-29T10:30:00+09:00",
          "created_at": "2025-10-30T10:30:28+09:00"
        }
      ]
    }
  ],
  "pagination": {
    "current_page": 1,
    "per_page": 20,
    "total_pages": 3,
    "total_count": 50
  }
}
```

**注意事項**:
- キャンセル済み（`status='cancelled'`）の変換は一覧から除外されます
- 削除済み（`is_deleted=True`）の変換も一覧から除外されます

---

#### GET /api/v1/gallery/{conversion_id}/

**説明**: 特定の変換詳細を取得

**リクエスト**:
```http
GET /api/v1/gallery/42/
```

**成功レスポンス (200 OK)**:
```json
{
  "status": "success",
  "conversion": {
    "id": 42,
    "original_image_url": "/media/uploads/user_1/original.jpg",
    "original_image_name": "original.jpg",
    "original_image_size": 2048576,
    "prompt": "背景を白い無地の背景に変更してください",
    "generation_count": 3,
    "aspect_ratio": "4:3",
    "status": "completed",
    "processing_time": 28.5,
    "error_message": null,
    "created_at": "2025-10-30T10:30:00+09:00",
    "generated_images": [
      {
        "id": 101,
        "image_url": "/media/generated/user_1/image_101.png",
        "image_name": "generated_101.png",
        "image_size": 1536000,
        "brightness_adjustment": 0,
        "expires_at": "2025-11-29T10:30:10+09:00",
        "created_at": "2025-10-30T10:30:10+09:00"
      },
      {
        "id": 102,
        "image_url": "/media/generated/user_1/image_102.png",
        "image_name": "generated_102.png",
        "image_size": 1612800,
        "brightness_adjustment": 0,
        "expires_at": "2025-11-29T10:30:18+09:00",
        "created_at": "2025-10-30T10:30:18+09:00"
      },
      {
        "id": 103,
        "image_url": "/media/generated/user_1/image_103.png",
        "image_name": "generated_103.png",
        "image_size": 1589248,
        "brightness_adjustment": 0,
        "expires_at": "2025-11-29T10:30:28+09:00",
        "created_at": "2025-10-30T10:30:28+09:00"
      }
    ]
  }
}
```

**エラーレスポンス (404 Not Found)**:
- キャンセル済み変換にアクセスした場合、404エラーを返します
```json
{
  "status": "error",
  "message": "変換が見つかりません"
}
```

---

#### DELETE /api/v1/gallery/{conversion_id}/

**説明**: 変換履歴と関連画像を削除

**リクエスト**:
```http
DELETE /api/v1/gallery/42/
```

**成功レスポンス (200 OK)**:
```json
{
  "success": true,
  "message": "変換履歴を削除しました",
  "data": {
    "deleted_images": 3
  }
}
```

---

#### GET /api/v1/gallery/images/{image_id}/

**説明**: 生成画像の詳細を取得

**リクエスト**:
```http
GET /api/v1/gallery/images/101/
```

**成功レスポンス (200 OK)**:
```json
{
  "status": "success",
  "image": {
    "id": 101,
    "image_url": "/media/generated/user_1/image_101.png",
    "image_name": "generated_101.png",
    "image_size": 1536000,
    "brightness_adjustment": 10,
    "expires_at": "2025-11-29T10:30:10+09:00",
    "created_at": "2025-10-30T10:30:10+09:00",
    "conversion": {
      "id": 42,
      "original_image_url": "/media/uploads/user_1/original.jpg",
      "aspect_ratio": "4:3",
      "prompt": "背景を白い無地の背景に変更してください"
    }
  }
}
```

**エラーレスポンス (404 Not Found)**:
- キャンセル済み変換の画像にアクセスした場合、404エラーを返します

---

#### DELETE /api/v1/gallery/images/{image_id}/

**説明**: 生成画像を削除

**リクエスト**:
```http
DELETE /api/v1/gallery/images/101/
```

**成功レスポンス (200 OK)**:
```json
{
  "success": true,
  "message": "画像を削除しました"
}
```

---

#### PATCH /api/v1/gallery/images/{image_id}/brightness/

**説明**: 画像の輝度を調整

**リクエスト**:
```http
PATCH /api/v1/gallery/images/101/brightness/
Content-Type: application/json

{
  "brightness_adjustment": 15
}
```

**リクエストボディ**:
| フィールド | 型 | 必須 | 説明 |
|----------|-----|-----|------|
| brightness_adjustment | integer | ○ | 輝度調整値 (-50 〜 +50) |

**成功レスポンス (200 OK)**:
```json
{
  "success": true,
  "data": {
    "image_id": 101,
    "brightness_adjustment": 15,
    "adjusted_image_url": "/media/generated/user_1/image_101_adj.png"
  },
  "message": "輝度を調整しました"
}
```

**バリデーション**:
- brightness_adjustment: -50 〜 +50 の整数

---

#### GET /api/v1/gallery/images/{image_id}/download/

**説明**: 画像をダウンロード

**リクエスト**:
```http
GET /api/v1/gallery/images/101/download/
```

**成功レスポンス (200 OK)**:
```http
Content-Type: image/png
Content-Disposition: attachment; filename="generated_20251030_103010.png"

<binary image data>
```

---

### 4. 利用状況

#### GET /api/v1/usage/

**説明**: ユーザーの利用状況を取得

**リクエスト**:
```http
GET /api/v1/usage/
```

**成功レスポンス (200 OK)**:
```json
{
  "success": true,
  "data": {
    "monthly_limit": 100,
    "monthly_used": 25,
    "remaining": 75,
    "usage_percentage": 25.0,
    "current_month": "2025-10",
    "reset_date": "2025-11-01T00:00:00+09:00"
  }
}
```

---

#### GET /api/v1/usage/history/

**説明**: 月別利用履歴を取得

**リクエスト**:
```http
GET /api/v1/usage/history/?months=6
```

**クエリパラメータ**:
| パラメータ | 型 | 必須 | 説明 |
|----------|-----|-----|------|
| months | integer | × | 取得する月数 (デフォルト: 6, 最大: 12) |

**成功レスポンス (200 OK)**:
```json
{
  "success": true,
  "data": {
    "history": [
      {
        "month": "2025-10",
        "limit": 100,
        "used": 25,
        "conversion_count": 8
      },
      {
        "month": "2025-09",
        "limit": 100,
        "used": 87,
        "conversion_count": 29
      },
      {
        "month": "2025-08",
        "limit": 100,
        "used": 100,
        "conversion_count": 34
      }
    ]
  }
}
```

---

## エラーハンドリング

### エラーコード一覧

| HTTPステータス | エラーコード | 説明 |
|--------------|------------|------|
| 400 | INVALID_REQUEST | リクエストが不正 |
| 400 | INVALID_FILE | ファイル形式またはサイズが不正 |
| 400 | VALIDATION_ERROR | バリデーションエラー |
| 401 | INVALID_CREDENTIALS | 認証情報が不正 |
| 401 | AUTHENTICATION_REQUIRED | 認証が必要 |
| 403 | QUOTA_EXCEEDED | 利用制限超過 |
| 403 | PERMISSION_DENIED | アクセス権限なし |
| 404 | NOT_FOUND | リソースが見つからない |
| 409 | CONFLICT | リソースの競合 |
| 413 | FILE_TOO_LARGE | ファイルサイズ超過 |
| 415 | UNSUPPORTED_MEDIA_TYPE | サポートされていないメディアタイプ |
| 429 | RATE_LIMIT_EXCEEDED | レート制限超過 |
| 500 | INTERNAL_SERVER_ERROR | サーバー内部エラー |
| 502 | API_ERROR | 外部API呼び出しエラー |
| 503 | SERVICE_UNAVAILABLE | サービス利用不可 |

### エラーレスポンス例

#### バリデーションエラー
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "入力値が不正です",
    "details": {
      "generation_count": [
        "この値は1以上5以下である必要があります"
      ],
      "prompt": [
        "このフィールドは必須です"
      ]
    }
  }
}
```

#### 利用制限超過
```json
{
  "success": false,
  "error": {
    "code": "QUOTA_EXCEEDED",
    "message": "今月の利用可能回数を超過しています",
    "details": {
      "monthly_limit": 100,
      "monthly_used": 100,
      "remaining": 0,
      "reset_date": "2025-11-01T00:00:00+09:00"
    }
  }
}
```

#### 外部APIエラー
```json
{
  "success": false,
  "error": {
    "code": "API_ERROR",
    "message": "画像生成APIでエラーが発生しました",
    "details": {
      "api_error": "Rate limit exceeded",
      "retry_after": 60
    }
  }
}
```

---

## レート制限

### 制限値

| エンドポイント | 制限 | ウィンドウ |
|-------------|-----|----------|
| `/api/v1/auth/login/` | 5回 | 1分 |
| `/api/v1/upload/` | 10回 | 1分 |
| `/api/v1/convert/` | 5回 | 1分 |
| その他のGET | 100回 | 1分 |

### レスポンスヘッダー

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1698652800
```

### 制限超過時のレスポンス

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json

{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "リクエスト数が制限を超えています",
    "details": {
      "retry_after": 30
    }
  }
}
```

---

## WebSocket仕様

### 接続エンドポイント

```
wss://your-domain.com/ws/conversion/{conversion_id}/
```

**注意**: `conversion_id`は数値ID（例: `42`）です。

### 認証・認可

- WebSocket接続時、Djangoセッション認証が自動的に適用されます
- 変換履歴の所有者のみ接続可能（他ユーザーの変換には接続できません）
- 未認証ユーザーは接続が拒否されます

### 接続例

#### 方法1: ConversionWebSocketクラスを使用（推奨）

```javascript
// websocket-client.jsが読み込まれている必要があります
const ws = new window.ConversionWebSocket(conversionId, {
  reconnectInterval: 3000,
  maxReconnectAttempts: 5,
  enableFallback: true,
  fallbackPollInterval: 4000,
});

// 進捗更新イベント
ws.on('progress', (data) => {
  console.log('進捗:', data.progress, '%');
  console.log('現在:', data.current, '/', data.total);
  console.log('メッセージ:', data.message);
});

// 完了イベント
ws.on('completed', (data) => {
  console.log('完了:', data.images);
});

// 失敗イベント
ws.on('failed', (data) => {
  console.error('失敗:', data.error);
});

// キャンセルイベント
ws.on('cancelled', (data) => {
  console.log('キャンセルされました');
});

// 接続開始
ws.connect();
```

#### 方法2: ネイティブWebSocket APIを使用

```javascript
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = `${protocol}//${window.location.host}/ws/conversion/${conversionId}/`;
const socket = new WebSocket(wsUrl);

socket.onopen = () => {
  console.log('WebSocket接続確立');
};

socket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('進捗更新:', data);
};

socket.onerror = (error) => {
  console.error('WebSocketエラー:', error);
};

socket.onclose = () => {
  console.log('WebSocket接続終了');
};
```

### メッセージ形式

#### 進捗更新
```json
{
  "type": "progress",
  "message": "生成画像を保存中... (2/5)",
  "progress": 75,
  "status": "processing",
  "current": 2,
  "currentCount": 2,
  "total": 5,
  "totalCount": 5
}
```

**フィールド説明**:
- `type`: メッセージタイプ（`"progress"`）
- `message`: 進捗メッセージ（日本語）
- `progress`: 進捗パーセンテージ（0-100）
- `status`: ステータス（`"processing"`）
- `current`: 現在処理中の画像番号（1から開始）
- `currentCount`: `current`の互換性フィールド（同じ値）
- `total`: 生成予定の総枚数
- `totalCount`: `total`の互換性フィールド（同じ値）

#### 完了通知
```json
{
  "type": "completed",
  "message": "画像変換が完了しました！",
  "images": [
    {
      "id": 101,
      "url": "/media/generated/user_1/image_101.png",
      "name": "generated_101.png",
      "description": ""
    },
    {
      "id": 102,
      "url": "/media/generated/user_1/image_102.png",
      "name": "generated_102.png",
      "description": ""
    }
  ]
}
```

#### 失敗通知
```json
{
  "type": "failed",
  "message": "画像変換に失敗しました",
  "error": "API rate limit exceeded"
}
```

#### キャンセル通知
```json
{
  "type": "cancelled",
  "message": "画像変換はキャンセルされました"
}
```

### フォールバック機能

`ConversionWebSocket`クラスは、WebSocket接続に失敗した場合、自動的にポーリング（HTTP API）にフォールバックします。

- **再接続試行**: 最大5回、3秒間隔で再接続を試みます
- **フォールバック**: 再接続に失敗した場合、4秒間隔で`GET /api/v1/convert/{conversion_id}/status/`をポーリングします
- **自動切り替え**: WebSocket接続が復旧した場合、自動的にWebSocketに戻ります

### 複数変換の同時監視

複数の変換を同時に監視する場合は、`MultipleConversionWebSocket`クラスを使用します：

```javascript
const wsManager = new window.MultipleConversionWebSocket([1, 2, 3], {
  reconnectInterval: 3000,
  maxReconnectAttempts: 5,
  enableFallback: true,
  fallbackPollInterval: 4000,
});

// 進捗更新イベント（変換ID付き）
wsManager.on('progress', ({ conversionId, progress, status, message, current, total }) => {
  console.log(`変換 ${conversionId}: ${current}/${total}`);
});

// 完了イベント（変換ID付き）
wsManager.on('completed', ({ conversionId, images }) => {
  console.log(`変換 ${conversionId} 完了:`, images);
});

wsManager.connect();
```

---

## ベストプラクティス

### 1. セキュリティ

#### CSRFトークンの取得と使用
```javascript
// Django標準のCSRFトークン取得
function getCsrfToken() {
  return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

// Fetch APIでの使用
fetch('/api/v1/convert/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': getCsrfToken()
  },
  credentials: 'include',  // Cookieを含める
  body: JSON.stringify(data)
});
```

#### セキュアなファイルダウンロード
```python
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required

@login_required
def download_image(request, image_id):
    image = get_object_or_404(GeneratedImage, id=image_id)

    # 権限チェック
    if image.conversion.user != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    # ファイルレスポンス
    response = FileResponse(open(image.image_path, 'rb'))
    response['Content-Disposition'] = f'attachment; filename="{image.image_name}"'
    return response
```

### 2. パフォーマンス最適化

#### キャッシュの活用
```python
from django.core.cache import cache
from django.views.decorators.cache import cache_page

# プロンプト一覧は1時間キャッシュ
@cache_page(60 * 60)
def get_prompts(request):
    # ...
    pass

# ユーザー利用状況は5分キャッシュ
def get_usage(request):
    cache_key = f'usage_{request.user.id}'
    usage = cache.get(cache_key)

    if usage is None:
        usage = calculate_usage(request.user)
        cache.set(cache_key, usage, 300)  # 5分

    return JsonResponse(usage)
```

#### データベースクエリ最適化
```python
from django.db.models import Prefetch

# N+1問題を回避
conversions = ImageConversion.objects.filter(
    user=request.user
).select_related(
    'user'
).prefetch_related(
    Prefetch(
        'generated_images',
        queryset=GeneratedImage.objects.filter(is_deleted=False)
    )
)
```

### 3. エラーハンドリング

#### 統一的なエラーレスポンス
```python
from django.http import JsonResponse
from functools import wraps

def api_error_handler(func):
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        try:
            return func(request, *args, **kwargs)
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'error': {
                    'code': 'VALIDATION_ERROR',
                    'message': str(e),
                    'details': e.message_dict if hasattr(e, 'message_dict') else {}
                }
            }, status=400)
        except PermissionDenied as e:
            return JsonResponse({
                'success': False,
                'error': {
                    'code': 'PERMISSION_DENIED',
                    'message': str(e)
                }
            }, status=403)
        except Exception as e:
            logger.exception('Unexpected error')
            return JsonResponse({
                'success': False,
                'error': {
                    'code': 'INTERNAL_SERVER_ERROR',
                    'message': 'サーバーエラーが発生しました'
                }
            }, status=500)
    return wrapper

@api_error_handler
def my_view(request):
    # ...
    pass
```

### 4. フロントエンド実装例

#### Fetch APIラッパー
```javascript
class APIClient {
  constructor(baseURL) {
    this.baseURL = baseURL;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      'X-CSRFToken': this.getCsrfToken(),
      ...options.headers
    };

    const config = {
      ...options,
      headers,
      credentials: 'include'
    };

    try {
      const response = await fetch(url, config);
      const data = await response.json();

      if (!response.ok) {
        throw new APIError(data.error, response.status);
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }
      throw new APIError({
        code: 'NETWORK_ERROR',
        message: 'ネットワークエラーが発生しました'
      }, 0);
    }
  }

  getCsrfToken() {
    const name = 'csrftoken';
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
      return parts.pop().split(';').shift();
    }
    return '';
  }

  async get(endpoint) {
    return this.request(endpoint, { method: 'GET' });
  }

  async post(endpoint, data) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  async delete(endpoint) {
    return this.request(endpoint, { method: 'DELETE' });
  }

  async patch(endpoint, data) {
    return this.request(endpoint, {
      method: 'PATCH',
      body: JSON.stringify(data)
    });
  }
}

class APIError extends Error {
  constructor(error, status) {
    super(error.message);
    this.code = error.code;
    this.details = error.details;
    this.status = status;
  }
}

// 使用例
const api = new APIClient('/api/v1');

try {
  const result = await api.post('/convert/', {
    upload_id: 'uuid-1234',
    prompt: '背景を白に変更',
    generation_count: 3
  });
  console.log('変換開始:', result);
} catch (error) {
  if (error instanceof APIError) {
    console.error('APIエラー:', error.code, error.message);
  }
}
```

---

## 実装上の注意点

### Django実装のポイント

#### 1. URLルーティング
```python
# urls.py
from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    # 認証
    path('auth/login/', views.login_view, name='login'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('auth/me/', views.me_view, name='me'),

    # 画像アップロード
    path('upload/', views.upload_view, name='upload'),
    path('upload/<str:upload_id>/', views.delete_upload_view, name='delete_upload'),

    # 変換
    path('convert/', views.convert_view, name='convert'),
    path('convert/<str:job_id>/status/', views.status_view, name='status'),
    path('prompts/', views.prompts_view, name='prompts'),

    # ギャラリー
    path('gallery/', views.gallery_list_view, name='gallery_list'),
    path('gallery/<int:conversion_id>/', views.gallery_detail_view, name='gallery_detail'),
    path('gallery/images/<int:image_id>/', views.image_detail_view, name='image_detail'),
    path('gallery/images/<int:image_id>/brightness/', views.brightness_view, name='brightness'),
    path('gallery/images/<int:image_id>/download/', views.download_view, name='download'),

    # 利用状況
    path('usage/', views.usage_view, name='usage'),
    path('usage/history/', views.usage_history_view, name='usage_history'),
]
```

#### 2. ビューのベストプラクティス
```python
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
import json

@require_http_methods(["POST"])
def login_view(request):
    try:
        data = json.loads(request.body)
        # ログイン処理
        return JsonResponse({
            'success': True,
            'user': { ... }
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': { ... }
        }, status=400)

@login_required
@require_http_methods(["GET"])
def gallery_list_view(request):
    # ギャラリー取得処理
    pass
```

---

**文書履歴**:
- 2025-10-30: 初版作成
- 2025-11-01: WebSocket仕様更新、キャンセル済み変換の除外処理を追加
