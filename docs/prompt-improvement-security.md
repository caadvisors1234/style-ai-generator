# プロンプト改善API セキュリティ対策

## 概要
プロンプト改善API (`/api/v1/prompts/improve/`) のセキュリティ脆弱性を修正しました。

## 修正前の問題点

### P1: 認証なしでの有料API利用
- **問題**: `@csrf_exempt` により、誰でも認証なしでAPIを呼び出せた
- **影響**:
  - 悪意のあるユーザーが無制限にGemini API（有料）を呼び出せる
  - APIクォータの消費
  - 予期しないコスト発生
  - DoS攻撃の可能性

### セキュリティリスク
- **OWASP**: A01:2021 - Broken Access Control
- **CVSSスコア**: 中～高（認証なし + 有料リソース消費）

## 修正内容

### 1. 認証の追加
```python
@require_http_methods(["POST"])
@login_required_api  # ← 追加
def improve_prompt(request):
    ...
```

- `@csrf_exempt` を削除
- `@login_required_api` デコレータを追加
- 未認証ユーザーには HTTP 401 を返す

### 2. DoS対策
```python
# プロンプトの長さ制限
if len(user_prompt) > 3000:
    return JsonResponse({
        'status': 'error',
        'message': 'プロンプトは3000文字以内で入力してください',
        'code': 'PROMPT_TOO_LONG'
    }, status=400)
```

- プロンプトの最大長を **3000文字** に制限
- 過度に長いリクエストによるリソース消費を防止
- 十分な長さのプロンプト入力を許可

### 3. エラーコードの追加
すべてのエラーレスポンスに `code` フィールドを追加：
- `AUTHENTICATION_REQUIRED`: 認証が必要
- `MISSING_PROMPT`: プロンプトが空
- `PROMPT_TOO_LONG`: プロンプトが長すぎる（3000文字超）
- `INVALID_JSON`: 無効なJSON
- `API_NOT_CONFIGURED`: API設定エラー
- `IMPROVEMENT_FAILED`: 改善処理エラー
- `INTERNAL_ERROR`: 内部エラー

### 4. フロントエンドの対応
```javascript
// CSRFトークンの送信
const response = await fetch(IMPROVE_API_URL, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': csrfToken,  // ← 追加
    'X-Requested-With': 'XMLHttpRequest',
  },
  credentials: 'include',
  body: JSON.stringify({ prompt }),
});

// エラーコードに応じた処理
if (data.code === 'AUTHENTICATION_REQUIRED') {
  throw new Error('ログインが必要です...');
}
```

## セキュリティ対策一覧

### 実装済み
- ✅ 認証必須（`@login_required_api`）
- ✅ CSRF保護（DjangoのCSRFミドルウェア）
- ✅ DoS対策（プロンプト最大長3000文字）
- ✅ 詳細なエラーコード
- ✅ セッション管理（Django標準）
- ✅ 監査ログ（ユーザーID、プロンプト長）

### 推奨される追加対策（将来的）
- ⚠️ レート制限（例: 1ユーザーあたり10回/分）
- ⚠️ IPベースのレート制限
- ⚠️ 異常検知（短時間での大量リクエスト）
- ⚠️ APIキーのローテーション機能

## テスト結果

### 認証テスト
```bash
# 認証なしでのアクセス → 403 Forbidden (CSRF)
curl -X POST http://localhost:18002/api/v1/prompts/improve/ \
  -H "Content-Type: application/json" \
  -d '{"prompt": "テスト"}'
# 結果: HTTP 403 (CSRF検証失敗)
```

### 正常系テスト
```bash
# ログインユーザーからのアクセス（ブラウザ経由）
# 結果: HTTP 200, プロンプト改善成功
```

## 影響範囲

### ユーザーへの影響
- **既存ユーザー**: ログイン済みであれば影響なし
- **未ログインユーザー**: APIにアクセス不可（期待通り）
- **使用制限**: なし（自由に利用可能）
- **プロンプト長**: 最大3000文字まで入力可能

### システムへの影響
- **セキュリティ**: 大幅に向上（認証必須、CSRF保護）
- **パフォーマンス**: 影響なし（認証チェックは軽量）
- **コスト**: 不正利用の防止により、予期しないコスト発生を防止

## 関連ファイル

### バックエンド
- `api/views/prompts.py`: `improve_prompt` 関数の修正
- `api/decorators.py`: `login_required_api` デコレータ（既存）

### フロントエンド
- `static/js/prompt-improver.js`: CSRFトークン送信、エラーハンドリング

### ドキュメント
- `docs/prompt-improvement-security.md`: 本ドキュメント

## 参考資料

- [OWASP Top 10 2021](https://owasp.org/Top10/)
- [Django CSRF Protection](https://docs.djangoproject.com/en/5.0/ref/csrf/)
- [Django Authentication](https://docs.djangoproject.com/en/5.0/topics/auth/)
