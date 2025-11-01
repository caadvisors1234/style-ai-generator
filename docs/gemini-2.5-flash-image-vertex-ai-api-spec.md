# Gemini 2.5 Flash Image API仕様書 (Vertex AI)

## 目次
1. [概要](#概要)
2. [認証](#認証)
3. [エンドポイント](#エンドポイント)
4. [リクエスト仕様](#リクエスト仕様)
5. [レスポンス仕様](#レスポンス仕様)
6. [実装例](#実装例)
7. [制限事項](#制限事項)

---

## 概要

### モデル情報
- **モデルID**: `gemini-2.5-flash-image`
- **提供元**: Google Cloud Vertex AI
- **機能**: テキストプロンプトからの画像生成、画像編集、スタイル転送
- **出力解像度**: 1024×1024（デフォルト）、最大1024×1792まで対応

### 主要機能
- テキストからの画像生成（Text-to-Image）
- 既存画像の編集（Image-to-Image）
- 画像スタイル転送
- マルチモーダル入力対応（テキスト + 画像）

---

## 認証

### Vertex AI認証方法

Vertex AIでは、Google Cloud認証情報を使用します。

#### 1. サービスアカウントの設定
```bash
# Google Cloud CLIで認証
gcloud auth application-default login

# または環境変数でサービスアカウントキーを指定
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

#### 2. 必要な権限
- `aiplatform.endpoints.predict`
- `aiplatform.endpoints.streamPredict`

#### 3. プログラム内での認証トークン取得
```python
from google.auth import default
import google.auth.transport.requests

credentials, project_id = default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
credentials.refresh(google.auth.transport.requests.Request())
access_token = credentials.token
```

---

## エンドポイント

### REST API エンドポイント構造

#### 標準生成エンドポイント（generateContent）
```
POST https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/publishers/google/models/gemini-2.5-flash-image:generateContent
```

#### ストリーミング生成エンドポイント（streamGenerateContent）
```
POST https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/publishers/google/models/gemini-2.5-flash-image:streamGenerateContent
```

### パラメータ
- `{PROJECT_ID}`: Google CloudプロジェクトID
- `{LOCATION}`: リージョン（例: `us-central1`, `global`）

### 推奨リージョン
- `us-central1`
- `global`（複数リージョンでの自動ルーティング）

---

## リクエスト仕様

### HTTPヘッダー
```http
Authorization: Bearer {ACCESS_TOKEN}
Content-Type: application/json
```

### リクエストボディ構造

```json
{
  "contents": [
    {
      "role": "user",
      "parts": [
        {
          "text": "プロンプトテキスト"
        },
        {
          "inlineData": {
            "mimeType": "image/png",
            "data": "base64エンコードされた画像データ"
          }
        }
      ]
    }
  ],
  "generationConfig": {
    "temperature": 0.8,
    "topP": 0.95,
    "topK": 40,
    "candidateCount": 1,
    "maxOutputTokens": 2048,
    "responseModalities": ["TEXT", "IMAGE"]
  },
  "safetySettings": [
    {
      "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
      "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    }
  ]
}
```

### パラメータ詳細

#### contents（必須）
会話の内容を含む配列。

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `role` | string | ○ | メッセージの送信者。`user`または`model` |
| `parts` | array | ○ | メッセージの各パート |

#### parts
メッセージの構成要素。

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `text` | string | △ | テキストプロンプト |
| `inlineData` | object | △ | インライン画像データ |
| `fileData` | object | △ | ファイル参照データ |

**注**: `text`、`inlineData`、`fileData`のいずれか1つ以上が必須

#### inlineData
Base64エンコードされた画像データ。

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `mimeType` | string | ○ | MIMEタイプ（`image/png`, `image/jpeg`） |
| `data` | string | ○ | Base64エンコードされた画像データ |

#### fileData
Google Cloud Storageに保存された画像ファイルの参照。

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `mimeType` | string | ○ | MIMEタイプ |
| `fileUri` | string | ○ | GCSファイルURI（`gs://bucket-name/file.png`） |

#### generationConfig（オプション）
生成パラメータの設定。

| パラメータ | 型 | デフォルト | 範囲 | 説明 |
|-----------|-----|-----------|------|------|
| `temperature` | float | 0.8 | 0.0-2.0 | ランダム性の制御。高いほど多様な出力 |
| `topP` | float | 0.95 | 0.0-1.0 | nucleus sampling |
| `topK` | integer | 40 | 1-100 | トップK選択 |
| `candidateCount` | integer | 1 | 1-4 | 生成する候補数 |
| `maxOutputTokens` | integer | 2048 | - | 最大出力トークン数 |
| `responseModalities` | array | - | - | 出力モダリティ。`["TEXT", "IMAGE"]`を指定 |

**重要**: 画像生成の場合、`responseModalities`に`["TEXT", "IMAGE"]`を含める必要があります。

#### safetySettings（オプション）
安全性フィルタの設定。

| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `category` | enum | 安全性カテゴリ |
| `threshold` | enum | ブロック閾値 |

**安全性カテゴリ**:
- `HARM_CATEGORY_HATE_SPEECH`
- `HARM_CATEGORY_DANGEROUS_CONTENT`
- `HARM_CATEGORY_HARASSMENT`
- `HARM_CATEGORY_SEXUALLY_EXPLICIT`

**ブロック閾値**:
- `BLOCK_NONE`: ブロックなし
- `BLOCK_ONLY_HIGH`: 高確率のみブロック
- `BLOCK_MEDIUM_AND_ABOVE`: 中確率以上をブロック
- `BLOCK_LOW_AND_ABOVE`: 低確率以上をブロック

---

## レスポンス仕様

### 成功レスポンス（200 OK）

```json
{
  "candidates": [
    {
      "content": {
        "parts": [
          {
            "text": "生成された説明テキスト"
          },
          {
            "inlineData": {
              "mimeType": "image/png",
              "data": "base64エンコードされた画像データ"
            }
          }
        ],
        "role": "model"
      },
      "finishReason": "STOP",
      "index": 0,
      "safetyRatings": [
        {
          "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
          "probability": "NEGLIGIBLE",
          "blocked": false
        }
      ]
    }
  ],
  "usageMetadata": {
    "promptTokenCount": 15,
    "candidatesTokenCount": 250,
    "totalTokenCount": 265
  },
  "modelVersion": "gemini-2.5-flash-image-001"
}
```

### レスポンスフィールド

#### candidates
生成された候補のリスト。

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `content` | object | 生成されたコンテンツ |
| `finishReason` | enum | 生成停止理由 |
| `index` | integer | 候補のインデックス |
| `safetyRatings` | array | 安全性評価 |

#### finishReason
生成が停止した理由。

- `STOP`: 正常に完了
- `MAX_TOKENS`: 最大トークン数に到達
- `SAFETY`: 安全性フィルタによりブロック
- `RECITATION`: 引用検出によりブロック

#### parts（レスポンス内）
生成されたコンテンツの各パート。

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `text` | string | 生成されたテキスト |
| `inlineData` | object | 生成された画像データ |

#### usageMetadata
トークン使用量の情報。

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `promptTokenCount` | integer | プロンプトのトークン数 |
| `candidatesTokenCount` | integer | 生成された候補のトークン数 |
| `totalTokenCount` | integer | 合計トークン数 |

---

## 実装例

### Python（google-genai SDK）

#### 基本的な画像生成

```python
from google import genai
from google.genai.types import GenerateContentConfig, Modality, HttpOptions
from PIL import Image
from io import BytesIO

# Vertex AI用のクライアント初期化
client = genai.Client(
    vertexai=True,
    project='your-project-id',
    location='us-central1',
    http_options=HttpOptions(api_version='v1')
)

# 画像生成リクエスト
response = client.models.generate_content(
    model='gemini-2.5-flash-image',
    contents='A minimalist composition featuring a single red maple leaf',
    config=GenerateContentConfig(
        response_modalities=[Modality.TEXT, Modality.IMAGE],
        candidate_count=1,
        temperature=0.8
    )
)

# 画像データの抽出と保存
for part in response.candidates[0].content.parts:
    if part.inline_data is not None:
        image = Image.open(BytesIO(part.inline_data.data))
        image.save('generated_image.png')
        print('画像を保存しました: generated_image.png')
```

#### 画像編集

```python
from PIL import Image
import io

# 元画像の読み込み
with open('input_image.png', 'rb') as f:
    image_data = f.read()

# Base64エンコード
import base64
image_base64 = base64.b64encode(image_data).decode('utf-8')

# 画像編集リクエスト
response = client.models.generate_content(
    model='gemini-2.5-flash-image',
    contents=[
        {
            'parts': [
                {
                    'inline_data': {
                        'mime_type': 'image/png',
                        'data': image_base64
                    }
                },
                {
                    'text': 'Change the blue sofa to a vintage brown leather chesterfield sofa'
                }
            ]
        }
    ],
    config=GenerateContentConfig(
        response_modalities=[Modality.TEXT, Modality.IMAGE]
    )
)

# 編集後の画像を保存
for part in response.candidates[0].content.parts:
    if part.inline_data is not None:
        image = Image.open(BytesIO(part.inline_data.data))
        image.save('edited_image.png')
```

### JavaScript（@google/genai SDK）

```javascript
import { GoogleGenAI } from '@google/genai';
import * as fs from 'node:fs';

// Vertex AI用のクライアント初期化
const ai = new GoogleGenAI({
  vertexai: true,
  project: 'your-project-id',
  location: 'us-central1'
});

// 画像生成リクエスト
async function generateImage() {
  const prompt = 'A modern minimalist logo for a coffee shop';
  
  const response = await ai.models.generateContent({
    model: 'gemini-2.5-flash-image',
    contents: prompt,
    config: {
      responseModalities: ['TEXT', 'IMAGE']
    }
  });
  
  // 画像データの抽出と保存
  for (const part of response.candidates[0].content.parts) {
    if (part.inlineData) {
      const imageData = part.inlineData.data;
      const buffer = Buffer.from(imageData, 'base64');
      fs.writeFileSync('generated_image.png', buffer);
      console.log('画像を保存しました: generated_image.png');
    }
  }
}

generateImage();
```

### Go

```go
package main

import (
    "context"
    "fmt"
    "os"
    "google.golang.org/genai"
)

func main() {
    ctx := context.Background()
    
    // Vertex AI用のクライアント初期化
    client, err := genai.NewClient(ctx, &genai.ClientConfig{
        Project:  "your-project-id",
        Location: "us-central1",
        Backend:  genai.BackendVertexAI,
    })
    if err != nil {
        panic(err)
    }
    defer client.Close()
    
    // 画像生成リクエスト
    prompt := "A minimalist composition featuring a red maple leaf"
    
    result, err := client.Models.GenerateContent(
        ctx,
        "gemini-2.5-flash-image",
        genai.Text(prompt),
        &genai.GenerateContentConfig{
            ResponseModalities: []genai.Modality{
                genai.ModalityText,
                genai.ModalityImage,
            },
        },
    )
    if err != nil {
        panic(err)
    }
    
    // 画像データの抽出と保存
    for _, part := range result.Candidates[0].Content.Parts {
        if part.InlineData != nil {
            imageBytes := part.InlineData.Data
            outputFilename := "generated_image.png"
            err := os.WriteFile(outputFilename, imageBytes, 0644)
            if err != nil {
                panic(err)
            }
            fmt.Println("画像を保存しました:", outputFilename)
        }
    }
}
```

### cURL（REST API直接呼び出し）

```bash
# 環境変数の設定
export PROJECT_ID="your-project-id"
export LOCATION="us-central1"
export ACCESS_TOKEN=$(gcloud auth application-default print-access-token)

# 画像生成リクエスト
curl -X POST \
  "https://${LOCATION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION}/publishers/google/models/gemini-2.5-flash-image:generateContent" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [
      {
        "role": "user",
        "parts": [
          {
            "text": "Create a minimalist logo for a coffee shop"
          }
        ]
      }
    ],
    "generationConfig": {
      "temperature": 0.8,
      "responseModalities": ["TEXT", "IMAGE"],
      "candidateCount": 1
    }
  }' | jq -r '.candidates[0].content.parts[] | select(.inlineData) | .inlineData.data' | base64 --decode > generated_image.png
```

#### 画像編集用cURL

```bash
# 画像をBase64エンコード
IMG_PATH="input_image.png"
IMG_BASE64=$(base64 -w0 "$IMG_PATH")

# 画像編集リクエスト
curl -X POST \
  "https://${LOCATION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION}/publishers/google/models/gemini-2.5-flash-image:generateContent" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"contents\": [
      {
        \"role\": \"user\",
        \"parts\": [
          {
            \"inlineData\": {
              \"mimeType\": \"image/png\",
              \"data\": \"$IMG_BASE64\"
            }
          },
          {
            \"text\": \"Change the blue sofa to a vintage brown leather chesterfield sofa\"
          }
        ]
      }
    ],
    \"generationConfig\": {
      \"responseModalities\": [\"TEXT\", \"IMAGE\"]
    }
  }" | jq -r '.candidates[0].content.parts[] | select(.inlineData) | .inlineData.data' | base64 --decode > edited_image.png
```

---

## 制限事項

### 技術的制限

#### サイズ制限
- **インライン画像データ**: 最大20MB
- **出力画像解像度**: 
  - デフォルト: 1024×1024
  - 最大: 1024×1792

#### レート制限
- リージョンやプロジェクトによって異なる
- Vertex AIのクォータ管理コンソールで確認可能
- 制限超過時は429エラーが返される

#### トークン制限
- 最大入力トークン数: モデル仕様に依存
- 最大出力トークン数: 設定可能（`maxOutputTokens`パラメータ）

### 対応形式

#### 入力画像形式
- PNG (`image/png`)
- JPEG (`image/jpeg`)
- WebP (`image/webp`)
- GIF (`image/gif`)

#### 出力画像形式
- PNG (`image/png`) - Base64エンコード形式

### 重要な注意事項

1. **responseModalities必須**: 
   - 画像生成には`responseModalities: ["TEXT", "IMAGE"]`が必須
   - 画像のみの出力は非対応（テキストも含める必要あり）

2. **認証**: 
   - Vertex AI使用時は、Google Cloud認証情報が必須
   - APIキーではなく、サービスアカウントまたはユーザー認証を使用

3. **リージョン選択**: 
   - `global`エンドポイントは自動ルーティングを提供
   - 特定リージョンを指定することも可能

4. **エラーハンドリング**: 
   - 429エラー: レート制限超過（リトライ推奨）
   - 400エラー: リクエスト形式エラー
   - 403エラー: 認証または権限エラー
   - 500エラー: サーバーエラー（リトライ推奨）

5. **コスト**: 
   - 入力トークンと出力トークンで課金
   - 画像生成は追加コストが発生
   - 詳細はVertex AI料金ページを参照

### ベストプラクティス

1. **プロンプト設計**: 
   - 具体的で詳細な説明を提供
   - スタイル、色、構図を明確に指定
   - ネガティブプロンプトも活用

2. **エラーハンドリング**: 
   - Exponential backoffを実装
   - 適切なタイムアウト設定
   - ログ記録の実装

3. **パフォーマンス最適化**: 
   - 画像サイズの最適化
   - キャッシュの活用
   - バッチ処理の検討

4. **セキュリティ**: 
   - サービスアカウントキーの安全な管理
   - 最小権限の原則を適用
   - APIアクセスログの監視

### 実装テンプレートとの対応

- 実際の生成プロンプトは `images/services/gemini_image_api.py` の `GeminiImageAPIService._build_variation_prompt()` で組み立てている。
  - 本ドキュメントのベストプラクティス（具体性・スタイル指定・品質維持・禁止事項）を組み込み済み。
  - バリエーション別の追加指示はアプリ側の要件（サロン向け広告／カタログ用途）に合わせて再定義している。
- テンプレートを調整する場合は、上記関数の文言を編集したうえで、ここに追記されているポリシーとの差分（必須要件・禁止事項など）が崩れていないか確認すること。
- ネガティブプロンプトや追加スタイルガイドを導入した際は、差分をこの節に追記し、更新履歴を残す。

---

## 参考リンク

- [Vertex AI ドキュメント](https://cloud.google.com/vertex-ai/docs)
- [Gemini API リファレンス](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/inference)
- [Google Cloud 認証ガイド](https://cloud.google.com/docs/authentication)
- [Vertex AI 料金](https://cloud.google.com/vertex-ai/pricing)

---

## バージョン情報

- **作成日**: 2025-10-30
- **APIバージョン**: v1
- **モデル**: gemini-2.5-flash-image
- **SDK バージョン**: 
  - Python: google-genai (最新版)
  - JavaScript: @google/genai (最新版)
  - Go: google.golang.org/genai (最新版)
