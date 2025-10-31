"""
WebSocket routing configuration for image conversion progress tracking.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(
        r'ws/conversion/(?P<conversion_id>\d+)/$',
        consumers.ImageConversionConsumer.as_asgi()
    ),
]
