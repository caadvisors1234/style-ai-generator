from django.urls import path
from . import views

app_name = 'frontend'

urlpatterns = [
    path('login/', views.LoginPageView.as_view(), name='login'),
    path('', views.MainPageView.as_view(), name='main'),
    path('processing/<int:conversion_id>/', views.ProcessingPageView.as_view(), name='processing'),
    path('processing/multiple/', views.ProcessingMultiplePageView.as_view(), name='processing_multiple'),
    path('gallery/', views.GalleryPageView.as_view(), name='gallery'),
]
