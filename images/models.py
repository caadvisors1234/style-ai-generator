"""
Image conversion models for the image conversion system.
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid
import os


def upload_image_path(instance, filename):
    """
    アップロード画像の保存パスを生成

    Args:
        instance: モデルインスタンス
        filename: 元のファイル名

    Returns:
        str: 保存パス
    """
    ext = os.path.splitext(filename)[1]
    new_filename = f"{uuid.uuid4()}{ext}"
    return f"uploads/user_{instance.user.id}/{new_filename}"


def generated_image_path(instance, filename):
    """
    生成画像の保存パスを生成

    Args:
        instance: GeneratedImageインスタンス
        filename: ファイル名

    Returns:
        str: 保存パス
    """
    ext = os.path.splitext(filename)[1]
    new_filename = f"{uuid.uuid4()}{ext}"
    return f"generated/user_{instance.conversion.user.id}/{new_filename}"


ASPECT_RATIO_KEEP_ORIGINAL = 'original'
ASPECT_RATIO_CHOICES = [
    (ASPECT_RATIO_KEEP_ORIGINAL, '元画像の比率を維持'),
    ('1:1', '1:1'),
    ('3:4', '3:4'),
    ('4:3', '4:3'),
    ('9:16', '9:16'),
    ('16:9', '16:9'),
    ('3:2', '3:2'),
    ('2:3', '2:3'),
    ('21:9', '21:9'),
    ('9:21', '9:21'),
    ('4:5', '4:5'),
]

DEFAULT_ASPECT_RATIO = ASPECT_RATIO_KEEP_ORIGINAL


class ImageConversion(models.Model):
    """
    画像変換履歴テーブル
    画像変換処理の履歴を記録するメインテーブル
    """
    STATUS_CHOICES = [
        ('pending', '処理待ち'),
        ('processing', '処理中'),
        ('completed', '完了'),
        ('failed', '失敗'),
        ('cancelled', 'キャンセル'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='conversions',
        verbose_name='ユーザー'
    )
    original_image_path = models.CharField(
        max_length=500,
        verbose_name='元画像パス'
    )
    original_image_name = models.CharField(
        max_length=255,
        verbose_name='元画像ファイル名'
    )
    original_image_size = models.IntegerField(
        verbose_name='元画像サイズ（バイト）'
    )
    prompt = models.TextField(
        verbose_name='使用プロンプト',
        help_text='画像変換に使用したプロンプト'
    )
    model_name = models.CharField(
        max_length=100,
        default='gemini-2.5-flash-image',
        verbose_name='モデル名',
        help_text='画像生成に使用したモデル'
    )
    preset_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='プリセットID',
        help_text='選択されたプリセットのID'
    )
    preset_name = models.CharField(
        max_length=150,
        null=True,
        blank=True,
        verbose_name='プリセット表示名',
        help_text='選択されたプリセットの表示名（日本語）'
    )
    generation_count = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='生成枚数',
        help_text='生成する画像の枚数（1-5枚）'
    )
    usage_consumed = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name='消費クレジット',
        help_text='この変換で消費したクレジット数'
    )
    aspect_ratio = models.CharField(
        max_length=10,
        choices=ASPECT_RATIO_CHOICES,
        default=DEFAULT_ASPECT_RATIO,
        verbose_name='画像比率',
        help_text='生成する画像のアスペクト比'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='処理ステータス'
    )
    processing_time = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name='処理時間（秒）'
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        verbose_name='エラーメッセージ'
    )
    is_deleted = models.BooleanField(
        default=False,
        verbose_name='削除フラグ'
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
        db_table = 'image_conversion'
        db_table_comment = '画像変換履歴テーブル'
        verbose_name = '画像変換履歴'
        verbose_name_plural = '画像変換履歴'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['is_deleted', '-created_at']),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.prompt[:30]} ({self.status})'

    @property
    def job_id(self):
        """ジョブIDを返す（タスク追跡用）"""
        return f"job_{self.id}"

    def mark_as_processing(self):
        """処理中ステータスに更新"""
        self.status = 'processing'
        self.save(update_fields=['status', 'updated_at'])

    def mark_as_completed(self, processing_time):
        """
        完了ステータスに更新

        Args:
            processing_time (float): 処理時間（秒）
        """
        self.status = 'completed'
        self.processing_time = processing_time
        self.save(update_fields=['status', 'processing_time', 'updated_at'])

    def mark_as_failed(self, error_message):
        """
        失敗ステータスに更新

        Args:
            error_message (str): エラーメッセージ
        """
        self.status = 'failed'
        self.error_message = error_message
        self.save(update_fields=['status', 'error_message', 'updated_at'])

    def mark_as_cancelled(self):
        """キャンセルステータスに更新"""
        self.status = 'cancelled'
        self.save(update_fields=['status', 'updated_at'])


class GeneratedImage(models.Model):
    """
    生成画像テーブル
    AI生成された画像を管理するテーブル
    """
    conversion = models.ForeignKey(
        ImageConversion,
        on_delete=models.CASCADE,
        related_name='generated_images',
        verbose_name='変換履歴'
    )
    image_path = models.CharField(
        max_length=500,
        verbose_name='画像パス'
    )
    image_name = models.CharField(
        max_length=255,
        verbose_name='画像ファイル名'
    )
    image_size = models.IntegerField(
        verbose_name='画像サイズ（バイト）'
    )
    brightness_adjustment = models.IntegerField(
        default=0,
        validators=[MinValueValidator(-50), MaxValueValidator(50)],
        verbose_name='輝度調整値',
        help_text='輝度調整値（-50〜+50）'
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='削除予定日時',
        help_text='保持期限。未設定の場合は自動削除しません'
    )
    is_deleted = models.BooleanField(
        default=False,
        verbose_name='削除フラグ'
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
        db_table = 'generated_image'
        db_table_comment = '生成画像テーブル'
        verbose_name = '生成画像'
        verbose_name_plural = '生成画像'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversion', 'created_at']),
            models.Index(fields=['expires_at', 'is_deleted']),
            models.Index(fields=['is_deleted', '-created_at']),
        ]

    def __str__(self):
        return f'{self.image_name} (Conversion #{self.conversion.id})'

    def save(self, *args, **kwargs):
        """
        保存時の処理
        """
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """期限切れかどうかを返す"""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at

    @property
    def days_until_expiration(self):
        """削除までの残り日数を返す"""
        if not self.expires_at:
            return None
        delta = self.expires_at - timezone.now()
        return max(0, delta.days)

    def update_brightness(self, adjustment):
        """
        輝度調整値を更新

        Args:
            adjustment (int): 輝度調整値（-50〜+50）
        """
        self.brightness_adjustment = adjustment
        self.save(update_fields=['brightness_adjustment', 'updated_at'])


class PromptPreset(models.Model):
    """
    プロンプトプリセットテーブル
    ワンタッププロンプトの管理
    """
    CATEGORY_CHOICES = [
        ('composition', '構図'),
        ('hair_style', '髪型/スタイル'),
        ('hair_color', '髪色'),
        ('background', '背景'),
        ('texture', '質感'),
        ('tone', 'トーン'),
        ('other', 'その他'),
    ]

    name = models.CharField(
        max_length=100,
        verbose_name='プリセット名',
        help_text='プリセットの表示名'
    )
    prompt = models.TextField(
        verbose_name='プロンプト',
        help_text='実際にAPIに送信するプロンプト文'
    )
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='other',
        verbose_name='カテゴリ'
    )
    description = models.TextField(
        blank=True,
        verbose_name='説明',
        help_text='プリセットの詳細説明'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='有効フラグ',
        help_text='無効にするとUIに表示されなくなる'
    )
    display_order = models.IntegerField(
        default=0,
        verbose_name='表示順',
        help_text='小さい数字ほど前に表示される'
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
        db_table = 'prompt_preset'
        db_table_comment = 'プロンプトプリセットテーブル'
        verbose_name = 'プロンプトプリセット'
        verbose_name_plural = 'プロンプトプリセット'
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['is_active', 'display_order']),
            models.Index(fields=['category', 'is_active']),
        ]

    def __str__(self):
        return f'{self.name} ({self.get_category_display()})'



class UserFavoritePrompt(models.Model):
    """
    ユーザーのお気に入りプロンプトプリセット
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='favorite_prompts',
        verbose_name='ユーザー'
    )
    preset = models.ForeignKey(
        PromptPreset,
        on_delete=models.CASCADE,
        related_name='favorited_by',
        verbose_name='プリセット'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='登録日時'
    )

    class Meta:
        db_table = 'user_favorite_prompt'
        db_table_comment = 'ユーザーお気に入りプロンプトテーブル'
        verbose_name = 'お気に入りプロンプト'
        verbose_name_plural = 'お気に入りプロンプト'
        unique_together = [['user', 'preset']]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.preset.name}'
