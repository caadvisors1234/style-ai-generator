"""
API URLルーティング
"""

from django.urls import path
from .views import auth, convert, prompts, upload, gallery, usage, health, scrape, favorites


app_name = 'api'


urlpatterns = [
    # ヘルスチェックAPI
    path('v1/health/', health.health_check, name='health_check'),
    path('v1/ready/', health.readiness_check, name='readiness_check'),
    path('v1/alive/', health.liveness_check, name='liveness_check'),

    # 認証API
    path('v1/auth/csrf/', auth.csrf_token_view, name='csrf_token'),
    path('v1/auth/login/', auth.login_view, name='login'),
    path('v1/auth/logout/', auth.logout_view, name='logout'),
    path('v1/auth/me/', auth.me_view, name='me'),

    # アップロードAPI
    path('v1/upload/', upload.upload_images, name='upload_images'),
    path('v1/upload/delete/', upload.delete_upload, name='delete_upload'),
    path('v1/upload/validate/', upload.validate_upload, name='validate_upload'),

    # スクレイピングAPI
    path('v1/scrape/', scrape.scrape_from_url, name='scrape_from_url'),

    # 変換API
    path('v1/convert/', convert.convert_start, name='convert_start'),
    path('v1/convert/<int:conversion_id>/status/', convert.convert_status, name='convert_status'),
    path('v1/convert/<int:conversion_id>/cancel/', convert.convert_cancel, name='convert_cancel'),

    # プロンプトプリセットAPI
    path('v1/prompts/', prompts.prompts_list, name='prompts_list'),
    path('v1/prompts/categories/', prompts.prompts_categories, name='prompts_categories'),
    path('v1/prompts/improve/', prompts.improve_prompt, name='improve_prompt'),

    # お気に入りプロンプトAPI
    path('v1/prompts/favorites/', favorites.favorites_list, name='favorites_list'),
    path('v1/prompts/favorites/add/', favorites.favorites_add, name='favorites_add'),
    path('v1/prompts/favorites/<int:preset_id>/remove/', favorites.favorites_remove, name='favorites_remove'),

    # ギャラリーAPI
    path('v1/gallery/', gallery.gallery_list, name='gallery_list'),
    path('v1/gallery/<int:conversion_id>/', gallery.gallery_detail, name='gallery_detail'),
    path('v1/gallery/<int:conversion_id>/delete/', gallery.gallery_delete, name='gallery_delete'),
    path('v1/gallery/images/<int:image_id>/', gallery.image_detail, name='image_detail'),
    path('v1/gallery/images/<int:image_id>/delete/', gallery.image_delete, name='image_delete'),
    path('v1/gallery/images/<int:image_id>/download/', gallery.image_download, name='image_download'),
    path('v1/gallery/images/<int:image_id>/brightness/', gallery.image_brightness, name='image_brightness'),

    # 利用状況API
    path('v1/usage/', usage.usage_summary, name='usage_summary'),
    path('v1/usage/history/', usage.usage_history, name='usage_history'),
]
