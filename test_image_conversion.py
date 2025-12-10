#!/usr/bin/env python
"""
画像変換テストスクリプト

サンプル画像を使用してGemini 2.5 Flash Image APIの画像変換をテストします。
"""
import os
import sys
import django

# Django設定を読み込む
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from images.services.gemini_image_api import GeminiImageAPIService, GeminiImageAPIError


def test_image_conversion():
    """画像変換テスト"""
    print("=" * 70)
    print("Gemini 2.5 Flash Image - 画像変換テスト")
    print("=" * 70)
    print()

    # テスト画像のパス
    test_images = [
        {
            'path': 'test_uploads/style1.jpg',
            'name': 'style1.jpg',
            'prompt': 'この美容室の写真を、プロフェッショナルで高級感のあるスタイルに変換してください。明るく清潔感のある雰囲気を強調し、モダンで洗練された印象にしてください。'
        },
        {
            'path': 'test_uploads/style2.png',
            'name': 'style2.png',
            'prompt': 'この美容室の画像を、ナチュラルで温かみのある雰囲気に変換してください。柔らかい照明と落ち着いた色調で、リラックスできる空間を演出してください。'
        }
    ]

    # 各画像でテスト
    for idx, test_image in enumerate(test_images, 1):
        print(f"\n{'=' * 70}")
        print(f"テスト {idx}/{len(test_images)}: {test_image['name']}")
        print(f"{'=' * 70}")
        print(f"元画像: {test_image['path']}")
        print(f"プロンプト: {test_image['prompt'][:80]}...")
        print()

        try:
            # 画像が存在するか確認
            full_path = os.path.join('media', test_image['path'])
            if not os.path.exists(full_path):
                print(f"❌ エラー: 画像ファイルが見つかりません: {full_path}")
                continue

            print(f"[1/3] 画像変換を開始...")

            # 画像変換実行（3枚生成）
            results, model_used = GeminiImageAPIService.generate_images_from_reference(
                original_image_path=test_image['path'],
                prompt=test_image['prompt'],
                generation_count=3,
                aspect_ratio='4:3'
            )

            print(f"✅ {len(results)}枚の画像を生成しました（使用モデル: {model_used}）")
            print()

            # 生成画像を保存
            print(f"[2/3] 生成画像を保存中...")
            output_dir = f"test_generated/{os.path.splitext(test_image['name'])[0]}"

            for i, result in enumerate(results, 1):
                filename = f"generated_{i}.jpg"

                try:
                    relative_path = GeminiImageAPIService.save_generated_image(
                        image_data=result['image_data'],
                        output_dir=output_dir,
                        filename=filename
                    )

                    full_save_path = os.path.join('media', relative_path)
                    file_size = os.path.getsize(full_save_path)
                    file_size_kb = file_size / 1024

                    print(f"  ✅ 画像 {i}: {relative_path} ({file_size_kb:.1f} KB)")

                    if result.get('description'):
                        print(f"     説明: {result['description'][:100]}...")

                except Exception as e:
                    print(f"  ❌ 画像 {i} の保存に失敗: {str(e)}")

            print()
            print(f"[3/3] テスト完了")
            print(f"✅ {test_image['name']} の変換が成功しました！")
            print(f"   保存先: media/{output_dir}/")

        except GeminiImageAPIError as e:
            print(f"❌ Gemini APIエラー: {str(e)}")
            import traceback
            traceback.print_exc()

        except Exception as e:
            print(f"❌ 予期しないエラー: {str(e)}")
            import traceback
            traceback.print_exc()

    print()
    print("=" * 70)
    print("全テスト完了")
    print("=" * 70)
    print()
    print("生成画像の確認:")
    print("  - media/test_generated/style1/")
    print("  - media/test_generated/style2/")
    print()


if __name__ == '__main__':
    test_image_conversion()
