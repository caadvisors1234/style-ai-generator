"""
Images Admin設定
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.conf import settings
import os
from .models import ImageConversion, GeneratedImage, PromptPreset, UserFavoritePrompt


class GeneratedImageInline(admin.TabularInline):
    """生成画像のインライン表示"""
    model = GeneratedImage
    extra = 0
    can_delete = False

    fields = ('image_preview', 'image_name', 'image_size_display',
             'brightness_adjustment', 'expires_at', 'is_deleted')
    readonly_fields = ('image_preview', 'image_size_display',
                      'created_at', 'updated_at')

    def image_preview(self, obj):
        """画像プレビュー"""
        if obj.image_path:
            image_url = f"{settings.MEDIA_URL}{obj.image_path}"
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 100px; max-height: 100px;" /></a>',
                image_url,
                image_url
            )
        return '-'
    image_preview.short_description = 'プレビュー'

    def image_size_display(self, obj):
        """ファイルサイズの表示（KB表示）"""
        if obj.image_size:
            size_kb = obj.image_size / 1024
            return f'{size_kb:.1f} KB'
        return '-'
    image_size_display.short_description = 'サイズ'


@admin.register(ImageConversion)
class ImageConversionAdmin(admin.ModelAdmin):
    """画像変換履歴管理"""

    list_display = ('id', 'user_link', 'prompt_excerpt', 'status_display',
                   'generation_count', 'processing_time_display', 'created_at')
    list_filter = ('status', 'created_at', 'is_deleted')
    search_fields = ('user__username', 'prompt')
    readonly_fields = ('original_image_preview', 'processing_time',
                      'created_at', 'updated_at')
    inlines = [GeneratedImageInline]

    fieldsets = (
        ('ユーザー情報', {
            'fields': ('user',)
        }),
        ('元画像情報', {
            'fields': ('original_image_preview', 'original_image_name',
                      'original_image_size', 'original_image_path')
        }),
        ('変換設定', {
            'fields': ('prompt', 'generation_count')
        }),
        ('処理状況', {
            'fields': ('status', 'processing_time', 'error_message')
        }),
        ('その他', {
            'fields': ('is_deleted', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['set_deleted', 'set_active']

    def user_link(self, obj):
        """ユーザー名リンク"""
        return format_html(
            '<a href="/admin/auth/user/{}/change/">{}</a>',
            obj.user.id,
            obj.user.username
        )
    user_link.short_description = 'ユーザー'
    user_link.admin_order_field = 'user__username'

    def prompt_excerpt(self, obj):
        """プロンプト抜粋表示"""
        if len(obj.prompt) > 50:
            return obj.prompt[:50] + '...'
        return obj.prompt
    prompt_excerpt.short_description = 'プロンプト'

    def status_display(self, obj):
        """ステータスの色付き表示"""
        status_colors = {
            'pending': 'gray',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'orange',
        }
        color = status_colors.get(obj.status, 'black')
        status_labels = {
            'pending': '待機中',
            'processing': '処理中',
            'completed': '完了',
            'failed': '失敗',
            'cancelled': 'キャンセル',
        }
        label = status_labels.get(obj.status, obj.status)
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            label
        )
    status_display.short_description = 'ステータス'
    status_display.admin_order_field = 'status'

    def processing_time_display(self, obj):
        """処理時間の表示"""
        if obj.processing_time:
            return f'{float(obj.processing_time):.2f}秒'
        return '-'
    processing_time_display.short_description = '処理時間'
    processing_time_display.admin_order_field = 'processing_time'

    def original_image_preview(self, obj):
        """元画像プレビュー"""
        if obj.original_image_path:
            image_url = f"{settings.MEDIA_URL}{obj.original_image_path}"
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 300px; max-height: 300px;" /></a>',
                image_url,
                image_url
            )
        return '-'
    original_image_preview.short_description = '元画像プレビュー'

    @admin.action(description='選択した変換を削除済みにする')
    def set_deleted(self, request, queryset):
        """論理削除"""
        updated = queryset.update(is_deleted=True)
        # 関連する生成画像も削除
        for conversion in queryset:
            conversion.generated_images.all().update(is_deleted=True)
        self.message_user(
            request,
            f'{updated}件の変換を削除済みにしました。'
        )

    @admin.action(description='選択した変換を有効にする')
    def set_active(self, request, queryset):
        """有効化"""
        updated = queryset.update(is_deleted=False)
        self.message_user(
            request,
            f'{updated}件の変換を有効にしました。'
        )


@admin.register(GeneratedImage)
class GeneratedImageAdmin(admin.ModelAdmin):
    """生成画像管理"""

    list_display = ('id', 'image_preview_thumb', 'conversion_link',
                   'image_name', 'brightness_adjustment',
                   'expires_at', 'is_deleted', 'created_at')
    list_filter = ('is_deleted', 'created_at', 'expires_at')
    search_fields = ('image_name', 'conversion__user__username')
    readonly_fields = ('image_preview', 'created_at', 'updated_at')

    fieldsets = (
        ('変換情報', {
            'fields': ('conversion',)
        }),
        ('画像情報', {
            'fields': ('image_preview', 'image_path', 'image_name', 'image_size')
        }),
        ('調整', {
            'fields': ('brightness_adjustment',)
        }),
        ('その他', {
            'fields': ('expires_at', 'is_deleted', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['set_deleted', 'set_active', 'extend_expiry']

    def conversion_link(self, obj):
        """変換履歴リンク"""
        return format_html(
            '<a href="/admin/images/imageconversion/{}/change/">変換 #{}</a>',
            obj.conversion.id,
            obj.conversion.id
        )
    conversion_link.short_description = '変換履歴'

    def image_preview_thumb(self, obj):
        """サムネイルプレビュー（リスト表示用）"""
        if obj.image_path:
            image_url = f"{settings.MEDIA_URL}{obj.image_path}"
            return format_html(
                '<img src="{}" style="max-width: 50px; max-height: 50px;" />',
                image_url
            )
        return '-'
    image_preview_thumb.short_description = 'プレビュー'

    def image_preview(self, obj):
        """画像プレビュー（詳細表示用）"""
        if obj.image_path:
            image_url = f"{settings.MEDIA_URL}{obj.image_path}"
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 500px; max-height: 500px;" /></a>',
                image_url,
                image_url
            )
        return '-'
    image_preview.short_description = '画像プレビュー'

    @admin.action(description='選択した画像を削除済みにする')
    def set_deleted(self, request, queryset):
        """論理削除"""
        updated = queryset.update(is_deleted=True)
        self.message_user(
            request,
            f'{updated}件の画像を削除済みにしました。'
        )

    @admin.action(description='選択した画像を有効にする')
    def set_active(self, request, queryset):
        """有効化"""
        updated = queryset.update(is_deleted=False)
        self.message_user(
            request,
            f'{updated}件の画像を有効にしました。'
        )

    @admin.action(description='選択した画像の有効期限を30日延長')
    def extend_expiry(self, request, queryset):
        """有効期限を延長"""
        from django.utils import timezone
        from datetime import timedelta

        for image in queryset:
            if image.expires_at:
                image.expires_at = image.expires_at + timedelta(days=30)
            else:
                image.expires_at = timezone.now() + timedelta(days=30)
            image.save()

        self.message_user(
            request,
            f'{queryset.count()}件の画像の有効期限を30日延長しました。'
        )


@admin.register(PromptPreset)
class PromptPresetAdmin(admin.ModelAdmin):
    """プロンプトプリセット管理"""

    list_display = ('name', 'category', 'is_active', 'display_order',
                   'created_at')
    list_filter = ('category', 'is_active', 'created_at')
    search_fields = ('name', 'prompt', 'description')
    list_editable = ('is_active', 'display_order')

    fieldsets = (
        ('基本情報', {
            'fields': ('name', 'category', 'description')
        }),
        ('プロンプト', {
            'fields': ('prompt',)
        }),
        ('表示設定', {
            'fields': ('is_active', 'display_order')
        }),
        ('タイムスタンプ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at', 'updated_at')

    actions = ['activate', 'deactivate']

    @admin.action(description='選択したプリセットを有効にする')
    def activate(self, request, queryset):
        """有効化"""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f'{updated}件のプリセットを有効にしました。'
        )

    @admin.action(description='選択したプリセットを無効にする')
    def deactivate(self, request, queryset):
        """無効化"""
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f'{updated}件のプリセットを無効にしました。'
        )


@admin.register(UserFavoritePrompt)
class UserFavoritePromptAdmin(admin.ModelAdmin):
    """ユーザーお気に入りプロンプト管理"""

    list_display = ('user_link', 'preset_name', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'preset__name')
    readonly_fields = ('created_at',)

    fieldsets = (
        ('お気に入り情報', {
            'fields': ('user', 'preset')
        }),
        ('タイムスタンプ', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def user_link(self, obj):
        """ユーザー名リンク"""
        return format_html(
            '<a href="/admin/auth/user/{}/change/">{}</a>',
            obj.user.id,
            obj.user.username
        )
    user_link.short_description = 'ユーザー'
    user_link.admin_order_field = 'user__username'

    def preset_name(self, obj):
        """プリセット名"""
        return obj.preset.name
    preset_name.short_description = 'プリセット'
    preset_name.admin_order_field = 'preset__name'


# Admin サイトのカスタマイズ
admin.site.site_header = '美容室画像変換システム 管理画面'
admin.site.site_title = '管理画面'
admin.site.index_title = 'ダッシュボード'
