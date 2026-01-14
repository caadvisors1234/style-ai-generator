"""
プロンプト改善サービスのテストスクリプト
"""

import os
import sys
import django

# Django設定を読み込み
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from images.services.prompt_improver import PromptImproverService, PromptImproverError


def test_connection():
    """API接続テスト"""
    print("=" * 60)
    print("プロンプト改善サービス - 接続テスト")
    print("=" * 60)

    api_key = settings.GEMINI_API_KEY
    if not api_key:
        print("❌ GEMINI_API_KEYが設定されていません")
        return False

    print(f"✓ API Key: {api_key[:10]}...")

    try:
        service = PromptImproverService(api_key=api_key)
        print("✓ サービス初期化成功")

        print("\n接続テスト中...")
        is_connected = service.test_connection()

        if is_connected:
            print("✅ 接続テスト成功！")
            return True
        else:
            print("❌ 接続テスト失敗")
            return False

    except Exception as e:
        print(f"❌ エラー: {e}")
        return False


def test_improve_prompt():
    """プロンプト改善テスト"""
    print("\n" + "=" * 60)
    print("プロンプト改善テスト")
    print("=" * 60)

    api_key = settings.GEMINI_API_KEY
    if not api_key:
        print("❌ GEMINI_API_KEYが設定されていません")
        return False

    # テストプロンプト
    test_prompts = [
        "女性、ロングヘア、カフェ",
        "美容室の写真、おしゃれ",
        "髪型、ナチュラル、明るい",
    ]

    try:
        service = PromptImproverService(api_key=api_key)

        for i, test_prompt in enumerate(test_prompts, 1):
            print(f"\n--- テスト {i} ---")
            print(f"元のプロンプト: {test_prompt}")

            try:
                improved = service.improve_prompt(test_prompt)
                print(f"改善後のプロンプト:\n{improved}")
                print("✅ 成功")

            except PromptImproverError as e:
                print(f"❌ 改善エラー: {e}")
                return False

        print("\n" + "=" * 60)
        print("✅ 全てのテストが成功しました！")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メイン実行"""
    print("\n🚀 プロンプト改善サービステスト開始\n")

    # 1. 接続テスト
    if not test_connection():
        print("\n❌ 接続テストに失敗しました")
        return

    # 2. プロンプト改善テスト
    if not test_improve_prompt():
        print("\n❌ プロンプト改善テストに失敗しました")
        return

    print("\n🎉 全てのテストが完了しました！")


if __name__ == "__main__":
    main()
