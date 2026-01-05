"""
月次使用回数リセット管理コマンド

毎月1日0時に実行され、全ユーザーの月次使用回数をリセットする。
Celery Beatから定期的に実行される想定。
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import UserProfile


class Command(BaseCommand):
    """
    月次使用回数をリセットする管理コマンド
    """
    help = '全ユーザーの月次使用回数をリセットします'

    def add_arguments(self, parser):
        """
        コマンドライン引数を追加

        Args:
            parser: ArgumentParser
        """
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='実際には更新せず、リセット対象のユーザー数のみ表示'
        )

    def handle(self, *args, **options):
        """
        コマンド実行処理

        Args:
            *args: 可変長引数
            **options: キーワード引数
        """
        dry_run = options.get('dry_run', False)

        # リセット対象のUserProfileを取得（使用回数が0より大きい）
        target_profiles = UserProfile.objects.filter(monthly_used__gt=0)

        count = target_profiles.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'[DRY RUN] {count}件のユーザープロフィールの月次使用回数をリセットします'
                )
            )

            # 実際にリセットされるユーザーの一覧を表示（最大10件）
            for profile in target_profiles[:10]:
                self.stdout.write(
                    f'  - User: {profile.user.username}, '
                    f'Current Usage: {profile.monthly_used}/{profile.monthly_limit}'
                )

            if count > 10:
                self.stdout.write(f'  ... and {count - 10} more users')

            return

        # 実際にリセット
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('リセット対象のユーザーはいません')
            )
            return

        # 一括更新
        updated_count = target_profiles.update(
            monthly_used=0,
            updated_at=timezone.now()
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'✓ {updated_count}件のユーザープロフィールの月次使用回数をリセットしました'
            )
        )

        # ログ出力用のメッセージ
        self.stdout.write(
            f'実行日時: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'
        )
