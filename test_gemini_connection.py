#!/usr/bin/env python
"""
Gemini 2.5 Flash Image API 接続テスト
"""
import os
import django

# Django設定を読み込む
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from images.services.gemini_image_api import GeminiImageAPIService


def main():
    print("=" * 60)
    print("Gemini 2.5 Flash Image API 接続テスト")
    print("=" * 60)
    print()

    # 環境変数の確認
    print("[1] 環境変数の確認")
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
    location = os.getenv('GOOGLE_CLOUD_LOCATION')
    credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

    print(f"  GOOGLE_CLOUD_PROJECT: {project_id}")
    print(f"  GOOGLE_CLOUD_LOCATION: {location}")
    print(f"  GOOGLE_APPLICATION_CREDENTIALS: {credentials_path}")
    print(f"  認証ファイル存在: {os.path.exists(credentials_path) if credentials_path else False}")
    print()

    # 接続テスト
    print("[2] API接続テスト")
    try:
        result = GeminiImageAPIService.test_connection()

        print(f"  結果: {'成功' if result['success'] else '失敗'}")
        print(f"  メッセージ: {result['message']}")
        print(f"  モデル名: {result['model_name']}")
        print(f"  プロジェクトID: {result['project_id']}")
        print(f"  ロケーション: {result['location']}")

        if result.get('has_image'):
            print(f"  画像生成: 成功")
        print()

        if result['success']:
            print("✅ Gemini 2.5 Flash Image APIへの接続に成功しました！")
        else:
            print("❌ 接続テストに失敗しました")
            print(f"   エラー: {result['message']}")

    except Exception as e:
        print(f"❌ エラーが発生しました: {str(e)}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 60)


if __name__ == '__main__':
    main()
