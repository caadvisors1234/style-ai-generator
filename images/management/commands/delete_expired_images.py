"""
期限切れ画像削除管理コマンド

デフォルトでは何も削除しません（永続保存方針）。
明示的に --force を指定した場合のみ、期限切れの物理ファイルを削除します。
"""

import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from images.models import GeneratedImage


class Command(BaseCommand):
    """
    期限切れ画像を削除する管理コマンド
    """
    help = '期限切れの生成画像を削除します（生成から30日経過）'

    def add_arguments(self, parser):
        """
        コマンドライン引数を追加

        Args:
            parser: ArgumentParser
        """
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際には削除せず、削除対象の画像数のみ表示'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='削除フラグが立っていない画像も期限切れなら削除'
        )

    def handle(self, *args, **options):
        """
        コマンド実行処理

        Args:
            *args: 可変長引数
            **options: キーワード引数
        """
        dry_run = options.get('dry_run', False)
        force = options.get('force', False)

        # 永続保存をデフォルトとするため、明示的な --force なしでは何もしない
        if not force:
            self.stdout.write(
                self.style.WARNING(
                    '画像は永続保存の方針です。削除を行う場合は --force を指定してください。'
                )
            )
            return

        now = timezone.now()

        # 期限切れの画像を取得
        expired_images = GeneratedImage.objects.filter(
            expires_at__lt=now
        )

        # forceオプションがない場合は、削除フラグが立っているもののみ対象
        if not force:
            expired_images = expired_images.filter(is_deleted=True)

        count = expired_images.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'[DRY RUN] {count}件の期限切れ画像を削除します'
                )
            )

            # 削除対象の画像情報を表示（最大10件）
            for image in expired_images[:10]:
                days_expired = (now - image.expires_at).days
                self.stdout.write(
                    f'  - ID: {image.id}, '
                    f'Name: {image.image_name}, '
                    f'Expired: {days_expired}日前, '
                    f'Size: {image.image_size} bytes, '
                    f'Path: {image.image_path}'
                )

            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more images')

            # 総削除予定サイズを計算
            total_size = sum(img.image_size for img in expired_images)
            total_size_mb = total_size / (1024 * 1024)
            self.stdout.write(
                self.style.WARNING(
                    f'総削除予定サイズ: {total_size_mb:.2f} MB'
                )
            )

            return

        # 削除対象がない場合
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('削除対象の期限切れ画像はありません')
            )
            return

        # 実際に削除
        deleted_count = 0
        deleted_size = 0
        error_count = 0

        for image in expired_images:
            try:
                # 物理ファイルのパス
                file_path = os.path.join(settings.MEDIA_ROOT, image.image_path)

                # ファイルサイズを記録
                deleted_size += image.image_size

                # 物理ファイルが存在する場合は削除
                if os.path.exists(file_path):
                    os.remove(file_path)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ 物理ファイル削除: {file_path}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠ 物理ファイルが見つかりません: {file_path}'
                        )
                    )

                # データベースから削除
                image.delete()
                deleted_count += 1

            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'✗ 削除エラー (ID: {image.id}): {str(e)}'
                    )
                )

        # 結果サマリー
        deleted_size_mb = deleted_size / (1024 * 1024)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== 削除完了 ==='))
        self.stdout.write(
            self.style.SUCCESS(
                f'✓ 削除成功: {deleted_count}件'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'✓ 削除サイズ: {deleted_size_mb:.2f} MB'
            )
        )

        if error_count > 0:
            self.stdout.write(
                self.style.ERROR(
                    f'✗ 削除失敗: {error_count}件'
                )
            )

        self.stdout.write(
            f'実行日時: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'
        )
