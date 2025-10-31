"""
認証API

ログイン、ログアウト、セッション確認などの認証関連APIエンドポイント。
"""

import logging
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
import json
from api.decorators import login_required_api


logger = logging.getLogger(__name__)


@require_http_methods(["POST"])
def login_view(request):
    """
    ログインAPI

    POST /api/v1/auth/login/

    Request:
        {
            "username": "string",
            "password": "string"
        }

    Response (Success):
        {
            "status": "success",
            "user": {
                "id": int,
                "username": "string",
                "email": "string"
            },
            "profile": {
                "monthly_limit": int,
                "monthly_used": int,
                "remaining": int
            }
        }

    Response (Error):
        {
            "status": "error",
            "message": "string"
        }
    """
    try:
        # リクエストボディをパース
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')

        # バリデーション
        if not username or not password:
            return JsonResponse({
                'status': 'error',
                'message': 'ユーザー名とパスワードは必須です'
            }, status=400)

        # 認証
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # ログイン処理
            login(request, user)

            # ユーザー情報と利用状況を取得
            profile = user.profile

            logger.info(f"User logged in: {username}")

            return JsonResponse({
                'status': 'success',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                },
                'profile': {
                    'monthly_limit': profile.monthly_limit,
                    'monthly_used': profile.monthly_used,
                    'remaining': profile.remaining
                }
            })
        else:
            logger.warning(f"Failed login attempt for username: {username}")
            return JsonResponse({
                'status': 'error',
                'message': 'ユーザー名またはパスワードが正しくありません'
            }, status=401)

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': '無効なリクエストデータです'
        }, status=400)

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'ログイン処理中にエラーが発生しました'
        }, status=500)


@require_http_methods(["POST"])
@login_required_api
def logout_view(request):
    """
    ログアウトAPI

    POST /api/v1/auth/logout/

    Response:
        {
            "status": "success",
            "message": "ログアウトしました"
        }
    """
    try:
        username = request.user.username
        logout(request)

        logger.info(f"User logged out: {username}")

        return JsonResponse({
            'status': 'success',
            'message': 'ログアウトしました'
        })

    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'ログアウト処理中にエラーが発生しました'
        }, status=500)


@require_http_methods(["GET"])
@login_required_api
def me_view(request):
    """
    セッション確認API

    GET /api/v1/auth/me/

    Response:
        {
            "status": "success",
            "user": {
                "id": int,
                "username": "string",
                "email": "string"
            },
            "profile": {
                "monthly_limit": int,
                "monthly_used": int,
                "remaining": int
            }
        }
    """
    try:
        user = request.user
        profile = user.profile

        return JsonResponse({
            'status': 'success',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            },
            'profile': {
                'monthly_limit': profile.monthly_limit,
                'monthly_used': profile.monthly_used,
                'remaining': profile.remaining
            }
        })

    except Exception as e:
        logger.error(f"Me view error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'ユーザー情報の取得中にエラーが発生しました'
        }, status=500)


@require_http_methods(["GET"])
@ensure_csrf_cookie
def csrf_token_view(request):
    """
    CSRFトークン取得API

    GET /api/v1/auth/csrf/

    Response:
        {
            "status": "success"
        }
    """
    return JsonResponse({
        'status': 'success'
    })
