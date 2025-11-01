"""
Accounts Admin設定
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    """UserProfileのインライン編集"""
    model = UserProfile
    can_delete = False
    verbose_name = 'ユーザープロフィール'
    verbose_name_plural = 'ユーザープロフィール'

    fieldsets = (
        ('利用制限', {
            'fields': ('monthly_limit', 'monthly_used', 'remaining_display')
        }),
        ('アカウント状態', {
            'fields': ('is_deleted',)
        }),
        ('タイムスタンプ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('remaining_display', 'created_at', 'updated_at')

    def remaining_display(self, obj):
        """残り利用回数の表示"""
        if obj.id:
            remaining = obj.remaining
            color = 'green' if remaining > 20 else 'orange' if remaining > 0 else 'red'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} 回</span>',
                color,
                remaining
            )
        return '-'
    remaining_display.short_description = '残り利用回数'


class CustomUserAdmin(BaseUserAdmin):
    """カスタムユーザー管理"""
    # フォームを明示的に指定
    form = UserChangeForm
    add_form = UserCreationForm

    inlines = (UserProfileInline,)

    list_display = ('username', 'email', 'first_name', 'last_name',
                   'is_staff', 'monthly_usage_display', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined')

    # パスワード変更リンクを含むreadonly_fields
    readonly_fields = ('password_change_link', 'last_login', 'date_joined')

    # フィールドセットを明示的に定義
    fieldsets = (
        (None, {
            'fields': ('username', 'password_change_link')
        }),
        ('個人情報', {
            'fields': ('first_name', 'last_name', 'email')
        }),
        ('権限', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('重要な日付', {
            'fields': ('last_login', 'date_joined')
        }),
    )

    def password_change_link(self, obj):
        """パスワード変更リンクを表示"""
        if obj.pk:
            change_password_url = reverse('admin:auth_user_password_change', args=[obj.pk])
            return mark_safe(
                f'<div style="margin-bottom: 10px;">'
                f'<span style="color: #666; font-size: 0.9em;">生のパスワードは格納されていないため、このユーザーのパスワードを確認する方法はありません。</span><br>'
                f'<a href="{change_password_url}" class="btn btn-primary" style="margin-top: 10px; display: inline-block; padding: 8px 16px; background-color: #417690; color: white; text-decoration: none; border-radius: 4px;">パスワードを変更</a>'
                f'</div>'
            )
        return '-'
    password_change_link.short_description = 'パスワード'

    def monthly_usage_display(self, obj):
        """月次利用状況の表示"""
        try:
            profile = obj.profile
            used = profile.monthly_used
            limit = profile.monthly_limit
            percentage = (used / limit * 100) if limit > 0 else 0

            if percentage >= 100:
                color = 'red'
            elif percentage >= 80:
                color = 'orange'
            else:
                color = 'green'

            return format_html(
                '<span style="color: {};">{} / {} ({}%)</span>',
                color,
                used,
                limit,
                int(percentage)
            )
        except UserProfile.DoesNotExist:
            return '-'
    monthly_usage_display.short_description = '月次利用状況'
    monthly_usage_display.admin_order_field = 'profile__monthly_used'


# Userモデルを再登録
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """ユーザープロフィール管理"""

    list_display = ('user_username', 'monthly_limit', 'monthly_used',
                   'remaining_display', 'is_deleted', 'created_at')
    list_filter = ('is_deleted', 'created_at', 'monthly_limit')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('remaining_display', 'created_at', 'updated_at')

    fieldsets = (
        ('ユーザー情報', {
            'fields': ('user',)
        }),
        ('利用制限', {
            'fields': ('monthly_limit', 'monthly_used', 'remaining_display')
        }),
        ('アカウント状態', {
            'fields': ('is_deleted',)
        }),
        ('タイムスタンプ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['reset_monthly_usage', 'set_deleted', 'set_active']

    def user_username(self, obj):
        """ユーザー名の表示"""
        return obj.user.username
    user_username.short_description = 'ユーザー名'
    user_username.admin_order_field = 'user__username'

    def remaining_display(self, obj):
        """残り利用回数の表示"""
        remaining = obj.remaining
        color = 'green' if remaining > 20 else 'orange' if remaining > 0 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} 回</span>',
            color,
            remaining
        )
    remaining_display.short_description = '残り利用回数'

    @admin.action(description='選択したユーザーの月次利用回数をリセット')
    def reset_monthly_usage(self, request, queryset):
        """月次利用回数を一括リセット"""
        updated = queryset.update(monthly_used=0)
        self.message_user(
            request,
            f'{updated}件のユーザーの月次利用回数をリセットしました。'
        )

    @admin.action(description='選択したユーザーのアカウントを停止する')
    def set_deleted(self, request, queryset):
        """アカウント停止"""
        count = 0
        for profile in queryset:
            profile.is_deleted = True
            profile.save()  # saveメソッドでUser.is_activeも自動的に更新される
            count += 1
        self.message_user(
            request,
            f'{count}件のユーザーのアカウントを停止しました。'
        )

    @admin.action(description='選択したユーザーのアカウント停止を解除する')
    def set_active(self, request, queryset):
        """アカウント停止解除"""
        count = 0
        for profile in queryset:
            profile.is_deleted = False
            profile.save()  # saveメソッドでUser.is_activeも自動的に更新される
            count += 1
        self.message_user(
            request,
            f'{count}件のユーザーのアカウント停止を解除しました。'
        )
