"""
画像アップロードAPI
"""
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from images.services.upload import ImageUploadService, UploadValidationError
from api.decorators import login_required_api


@require_http_methods(["POST"])
@login_required_api
def upload_images(request):
    """
    画像アップロード

    POST /api/v1/upload/

    Request:
        multipart/form-data
        - images: 画像ファイル（複数可、最大10ファイル）

    Response:
        {
            "status": "success",
            "uploaded_files": [
                {
                    "file_path": "uploads/1/abc123.jpg",
                    "file_name": "original.jpg",
                    "file_size": 1234567,
                    "thumbnail_path": "uploads/1/thumbnails/thumb_abc123.jpg",
                    "preview_url": "/media/uploads/1/abc123.jpg"
                }
            ],
            "count": 1
        }
    """
    try:
        # アップロードされたファイルを取得
        uploaded_files = request.FILES.getlist('images')

        if not uploaded_files:
            return JsonResponse({
                'status': 'error',
                'message': 'アップロードする画像を選択してください'
            }, status=400)

        # アップロード処理
        upload_service = ImageUploadService(user_id=request.user.id)
        results = upload_service.process_uploads(uploaded_files)

        # プレビューURL追加
        for result in results:
            result['preview_url'] = f"/media/{result['file_path']}"
            result['thumbnail_url'] = f"/media/{result['thumbnail_path']}"

        return JsonResponse({
            'status': 'success',
            'uploaded_files': results,
            'count': len(results)
        })

    except UploadValidationError as e:
        # バリデーションエラー
        error_data = e.args[0]
        if isinstance(error_data, dict):
            return JsonResponse({
                'status': 'error',
                'message': error_data.get('message'),
                'errors': error_data.get('errors', []),
                'success_count': error_data.get('success_count', 0)
            }, status=400)
        else:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'予期しないエラーが発生しました: {str(e)}'
        }, status=500)


@require_http_methods(["DELETE"])
@login_required_api
def delete_upload(request):
    """
    アップロード画像削除

    DELETE /api/v1/upload/delete/

    Request Body:
        {
            "file_path": "uploads/1/abc123.jpg"
        }

    Response:
        {
            "status": "success",
            "message": "画像を削除しました"
        }
    """
    try:
        # リクエストボディからfile_path取得
        data = json.loads(request.body)
        file_path = data.get('file_path')

        if not file_path:
            return JsonResponse({
                'status': 'error',
                'message': 'file_pathが指定されていません'
            }, status=400)

        # ユーザーのファイルかチェック（uploads/{user_id}/...の形式）
        if not file_path.startswith(f'uploads/{request.user.id}/'):
            return JsonResponse({
                'status': 'error',
                'message': '権限がありません'
            }, status=403)

        # ファイル削除
        upload_service = ImageUploadService(user_id=request.user.id)
        success = upload_service.delete_file(file_path)

        if success:
            return JsonResponse({
                'status': 'success',
                'message': '画像を削除しました'
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': '画像の削除に失敗しました'
            }, status=500)

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'予期しないエラーが発生しました: {str(e)}'
        }, status=500)


@require_http_methods(["POST"])
@login_required_api
def validate_upload(request):
    """
    ファイル事前検証API

    POST /api/v1/upload/validate/

    Request Body:
        {
            "filename": "test.jpg",
            "filesize": 1234567,
            "mimetype": "image/jpeg"
        }

    Response:
        {
            "status": "success",
            "valid": true
        }
        or
        {
            "status": "error",
            "valid": false,
            "message": "エラーメッセージ"
        }
    """
    try:
        data = json.loads(request.body)
        filename = data.get('filename')
        filesize = data.get('filesize')
        mimetype = data.get('mimetype')

        if not all([filename, filesize, mimetype]):
            return JsonResponse({
                'status': 'error',
                'valid': False,
                'message': '必須パラメータが不足しています'
            }, status=400)

        upload_service = ImageUploadService(user_id=request.user.id)

        # ファイルサイズチェック
        if filesize > upload_service.MAX_FILE_SIZE:
            return JsonResponse({
                'status': 'error',
                'valid': False,
                'message': f'ファイルサイズは{upload_service.MAX_FILE_SIZE // (1024*1024)}MB以下にしてください'
            })

        # MIMEタイプチェック
        if mimetype not in upload_service.ALLOWED_FORMATS:
            return JsonResponse({
                'status': 'error',
                'valid': False,
                'message': '対応していないファイル形式です。対応形式: JPEG, PNG, WebP, HEIC/HEIF'
            })

        # 拡張子チェック
        from pathlib import Path
        file_ext = Path(filename).suffix.lower()
        if file_ext not in upload_service.ALLOWED_EXTENSIONS:
            return JsonResponse({
                'status': 'error',
                'valid': False,
                'message': f'対応していないファイル拡張子です。対応拡張子: {", ".join(upload_service.ALLOWED_EXTENSIONS)}'
            })

        return JsonResponse({
            'status': 'success',
            'valid': True,
            'message': 'アップロード可能です'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'valid': False,
            'message': 'Invalid JSON'
        }, status=400)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'valid': False,
            'message': f'予期しないエラーが発生しました: {str(e)}'
        }, status=500)
