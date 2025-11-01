"""
HotPepper BeautyスクレイピングAPI
"""
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from api.decorators import login_required_api
from images.services.scraper import HPBScraperService, ScraperValidationError
from images.services.upload import UploadValidationError


@require_http_methods(["POST"])
@csrf_exempt
@login_required_api
def scrape_from_url(request):
    """
    HotPepper BeautyページのURLから画像を取得してアップロードする

    POST /api/v1/scrape/

    Request Body:
        {
            "url": "https://beauty.hotpepper.jp/style/L000000000/"
        }

    Response:
        {
            "status": "success",
            "uploaded_files": [...],
            "count": 3
        }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({
            "status": "error",
            "message": "Invalid JSON",
        }, status=400)

    target_url = (data or {}).get("url", "").strip()
    if not target_url:
        return JsonResponse({
            "status": "error",
            "message": "URLを入力してください。",
        }, status=400)

    scraper = HPBScraperService(user_id=request.user.id)

    try:
        uploaded_files = scraper.scrape_and_upload(target_url)
    except ScraperValidationError as exc:
        return JsonResponse({
            "status": "error",
            "message": str(exc),
        }, status=400)
    except UploadValidationError as exc:
        # アップロードサービスからのバリデーションエラーを400で返す
        return JsonResponse({
            "status": "error",
            "message": str(exc),
        }, status=400)
    except Exception:
        return JsonResponse({
            "status": "error",
            "message": "予期しないエラーが発生しました。",
        }, status=500)

    for item in uploaded_files:
        item["preview_url"] = f"/media/{item['file_path']}"
        item["thumbnail_url"] = f"/media/{item['thumbnail_path']}"

    return JsonResponse({
        "status": "success",
        "uploaded_files": uploaded_files,
        "count": len(uploaded_files),
    })
