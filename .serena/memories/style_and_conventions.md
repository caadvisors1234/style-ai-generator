# コーディング規約・スタイル
- Django 標準構造＋アプリ別責務分離 (accounts/images/api)。
- Docstring・コメントは日本語で機能概要を説明するスタイル。
- 型ヒントはサービス層で積極使用、ビューは Django 標準シグネチャ中心。
- ロガーをモジュール単位で取得し INFO/ERROR ログ出力。
- モデルは Meta で db_table / indexes / ordering を細かく設定し、プロパティや業務ロジックメソッドを持つ。
- API レスポンスは JSON 固定シェイプ (`status`, `message`, `data`) を踏襲。