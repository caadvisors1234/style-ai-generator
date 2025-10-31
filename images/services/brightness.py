"""
画像輝度調整サービス
"""
import os
from pathlib import Path
from PIL import Image, ImageEnhance
from django.conf import settings


class BrightnessAdjustmentError(Exception):
    """輝度調整エラー"""
    pass


class BrightnessAdjustmentService:
    """画像輝度調整サービス"""

    # 輝度調整範囲
    MIN_ADJUSTMENT = -50
    MAX_ADJUSTMENT = 50

    @classmethod
    def validate_adjustment(cls, adjustment: int) -> None:
        """
        輝度調整値のバリデーション

        Args:
            adjustment: 調整値（-50〜+50）

        Raises:
            BrightnessAdjustmentError: バリデーションエラー
        """
        if not isinstance(adjustment, int):
            raise BrightnessAdjustmentError('調整値は整数である必要があります')

        if adjustment < cls.MIN_ADJUSTMENT or adjustment > cls.MAX_ADJUSTMENT:
            raise BrightnessAdjustmentError(
                f'調整値は{cls.MIN_ADJUSTMENT}〜{cls.MAX_ADJUSTMENT}の範囲で指定してください'
            )

    @classmethod
    def calculate_brightness_factor(cls, adjustment: int) -> float:
        """
        輝度調整係数を計算

        Args:
            adjustment: 調整値（-50〜+50）

        Returns:
            輝度係数（0.5〜1.5）
        """
        # -50〜+50 を 0.5〜1.5 に変換
        # adjustment=0 → factor=1.0（変化なし）
        # adjustment=-50 → factor=0.5（50%暗く）
        # adjustment=+50 → factor=1.5（50%明るく）
        return 1.0 + (adjustment / 100.0)

    @classmethod
    def adjust_brightness(cls, image_path: str, adjustment: int) -> str:
        """
        画像の輝度を調整

        Args:
            image_path: 元画像の相対パス（MEDIA_ROOTからの相対パス）
            adjustment: 調整値（-50〜+50）

        Returns:
            調整済み画像の相対パス

        Raises:
            BrightnessAdjustmentError: 調整エラー
        """
        # バリデーション
        cls.validate_adjustment(adjustment)

        # adjustment=0の場合は何もしない
        if adjustment == 0:
            return image_path

        try:
            # フルパスに変換
            full_image_path = Path(settings.MEDIA_ROOT) / image_path

            if not full_image_path.exists():
                raise BrightnessAdjustmentError('画像ファイルが見つかりません')

            # 画像を開く
            with Image.open(full_image_path) as img:
                # 輝度調整係数計算
                brightness_factor = cls.calculate_brightness_factor(adjustment)

                # 輝度調整
                enhancer = ImageEnhance.Brightness(img)
                adjusted_img = enhancer.enhance(brightness_factor)

                # 調整済みファイル名生成
                # 例: generated_001.jpg → generated_001_brightness_+10.jpg
                adjusted_filename = cls._generate_adjusted_filename(
                    full_image_path.name,
                    adjustment
                )
                adjusted_path = full_image_path.parent / adjusted_filename

                # 調整済み画像を保存
                # RGBAの場合はRGBに変換
                if adjusted_img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', adjusted_img.size, (255, 255, 255))
                    if adjusted_img.mode == 'P':
                        adjusted_img = adjusted_img.convert('RGBA')
                    background.paste(
                        adjusted_img,
                        mask=adjusted_img.split()[-1] if adjusted_img.mode in ('RGBA', 'LA') else None
                    )
                    adjusted_img = background
                elif adjusted_img.mode != 'RGB':
                    adjusted_img = adjusted_img.convert('RGB')

                # 保存
                adjusted_img.save(adjusted_path, 'JPEG', quality=90, optimize=True)

            # 相対パスを返す
            relative_adjusted_path = str(
                adjusted_path.relative_to(settings.MEDIA_ROOT)
            )
            return relative_adjusted_path

        except FileNotFoundError:
            raise BrightnessAdjustmentError('画像ファイルが見つかりません')
        except Exception as e:
            raise BrightnessAdjustmentError(f'輝度調整に失敗しました: {str(e)}')

    @classmethod
    def _generate_adjusted_filename(cls, original_filename: str, adjustment: int) -> str:
        """
        調整済みファイル名を生成

        Args:
            original_filename: 元のファイル名
            adjustment: 調整値

        Returns:
            調整済みファイル名
        """
        stem = Path(original_filename).stem
        ext = Path(original_filename).suffix

        # 既に調整済みファイル名の場合は、その部分を削除
        if '_brightness_' in stem:
            stem = stem.split('_brightness_')[0]

        # 新しい調整済みファイル名
        sign = '+' if adjustment >= 0 else ''
        adjusted_filename = f"{stem}_brightness_{sign}{adjustment}{ext}"

        return adjusted_filename

    @classmethod
    def delete_adjusted_image(cls, image_path: str) -> bool:
        """
        調整済み画像を削除

        Args:
            image_path: 調整済み画像の相対パス

        Returns:
            削除成功したかどうか
        """
        try:
            full_path = Path(settings.MEDIA_ROOT) / image_path

            if full_path.exists() and '_brightness_' in full_path.name:
                full_path.unlink()
                return True

            return False

        except Exception as e:
            print(f"Adjusted image deletion error: {str(e)}")
            return False
