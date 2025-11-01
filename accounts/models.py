"""
User account models for the image conversion system.
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache


class UserProfile(models.Model):
    """
    ユーザープロファイル拡張テーブル
    Django標準のUserモデルを拡張し、システム固有の情報を保持
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='ユーザー'
    )
    monthly_limit = models.IntegerField(
        default=100,
        validators=[MinValueValidator(0)],
        verbose_name='月間利用可能回数',
        help_text='ユーザーが1ヶ月に生成できる画像の最大枚数'
    )
    monthly_used = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='当月利用済み回数',
        help_text='当月に既に生成した画像の枚数'
    )
    is_deleted = models.BooleanField(
        default=False,
        verbose_name='アカウント停止',
        help_text='チェックを入れるとアカウントが停止されます'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='作成日時'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='更新日時'
    )

    class Meta:
        db_table = 'user_profile'
        db_table_comment = 'ユーザープロファイル拡張テーブル'
        verbose_name = 'ユーザープロファイル'
        verbose_name_plural = 'ユーザープロファイル'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_deleted', 'created_at']),
        ]

    def __str__(self):
        return f'{self.user.username} Profile'

    @property
    def remaining(self):
        """残り利用可能回数を返す"""
        return max(0, self.monthly_limit - self.monthly_used)

    @property
    def usage_percentage(self):
        """利用率（パーセンテージ）を返す"""
        if self.monthly_limit == 0:
            return 0
        return (self.monthly_used / self.monthly_limit) * 100

    def can_generate(self, count=1):
        """
        指定枚数の画像生成が可能かチェック

        Args:
            count (int): 生成したい枚数

        Returns:
            bool: 生成可能な場合True
        """
        return self.remaining >= count

    def increment_usage(self, count=1):
        """
        利用回数を増加

        Args:
            count (int): 増加させる回数
        """
        self.monthly_used += count
        self.save(update_fields=['monthly_used', 'updated_at'])

    def reset_monthly_usage(self):
        """月間利用回数をリセット"""
        self.monthly_used = 0
        self.save(update_fields=['monthly_used', 'updated_at'])

    def invalidate_usage_cache(self):
        """利用状況キャッシュを無効化"""
        cache.delete(f'usage_summary:{self.user_id}')
        for months in range(1, 13):
            cache.delete(f'usage_history:{self.user_id}:{months}')

    def save(self, *args, **kwargs):
        # is_deletedの変更をUser.is_activeに反映
        update_user_active = False
        if self.pk:  # 既存のレコードの場合
            try:
                old_instance = UserProfile.objects.get(pk=self.pk)
                if old_instance.is_deleted != self.is_deleted:
                    # is_deletedが変更された場合、User.is_activeを同期
                    update_user_active = True
            except UserProfile.DoesNotExist:
                pass
        else:  # 新規作成の場合
            # is_deletedがTrueなら、User.is_activeをFalseに設定
            if self.is_deleted:
                update_user_active = True

        # UserProfile本体を保存
        super().save(*args, **kwargs)

        # User.is_activeを更新（シグナルの無限ループを防ぐため、保存後に実行）
        if update_user_active:
            # シグナルを発火させずにUserを更新
            User.objects.filter(pk=self.user_id).update(is_active=not self.is_deleted)

        self.invalidate_usage_cache()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Userモデル保存時にUserProfileを自動生成

    Args:
        sender: Userモデル
        instance: 保存されたUserインスタンス
        created: 新規作成かどうか
    """
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Userモデル保存時にUserProfileも保存

    Args:
        sender: Userモデル
        instance: 保存されたUserインスタンス
    """
    if hasattr(instance, 'profile'):
        instance.profile.save()
