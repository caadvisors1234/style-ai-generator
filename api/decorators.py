"""
API専用のデコレータ
"""

from functools import wraps
from django.http import JsonResponse


def login_required_api(view_func):
    """
    API向けのログイン必須デコレータ

    未認証の場合はJSONレスポンスで401を返す
    """

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'status': 'error',
                'message': '認証が必要です',
                'code': 'AUTHENTICATION_REQUIRED',
            }, status=401)
        return view_func(request, *args, **kwargs)

    return _wrapped
