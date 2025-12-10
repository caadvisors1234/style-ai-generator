"""
ギャラリーAPI
"""
import json
import os
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.conf import settings
from django.db.models import Q, Prefetch
from django.utils import timezone
from pathlib import Path
from images.models import ImageConversion, GeneratedImage
from images.services.brightness import BrightnessAdjustmentService, BrightnessAdjustmentError
from api.decorators import login_required_api


@require_http_methods(["GET"])
@login_required_api
def gallery_list(request):
    """
    ギャラリー一覧取得

    GET /api/v1/gallery/

    Query Parameters:
        - page: ページ番号（デフォルト: 1）
        - per_page: 1ページあたりの件数（デフォルト: 20、最大: 100）
        - search: プロンプト検索（部分一致）
        - sort: ソート順（created_at_desc, created_at_asc）

    Response:
        {
            "status": "success",
            "conversions": [{
                "id": 1,
                "original_image_url": "/media/uploads/1/abc.jpg",
                "prompt": "プロフェッショナル...",
                "generation_count": 3,
                "status": "completed",
                "created_at": "2025-10-31T12:00:00Z",
                "generated_images": [{
                    "id": 1,
                    "image_url": "/media/generated/1/xyz.jpg",
                    "thumbnail_url": "/media/generated/1/thumb_xyz.jpg"
                }]
            }],
            "pagination": {
                "current_page": 1,
                "per_page": 20,
                "total_pages": 5,
                "total_count": 100
            }
        }
    """
    try:
        # パラメータ取得
        page = int(request.GET.get('page', 1))
        per_page = min(int(request.GET.get('per_page', 20)), 100)
        search = request.GET.get('search', '').strip()
        sort = request.GET.get('sort', 'created_at_desc')

        # ユーザーの変換一覧を取得（削除済み・キャンセル済み除外）
        conversions = ImageConversion.objects.filter(
            user=request.user,
            is_deleted=False
        ).exclude(
            status='cancelled'
        ).select_related('user').prefetch_related(
            Prefetch(
                'generated_images',
                queryset=GeneratedImage.objects.filter(is_deleted=False)
            )
        )

        # 検索フィルタ
        if search:
            conversions = conversions.filter(
                Q(prompt__icontains=search) | Q(preset_name__icontains=search)
            )

        # ソート
        if sort == 'created_at_asc':
            conversions = conversions.order_by('created_at')
        else:  # created_at_desc
            conversions = conversions.order_by('-created_at')

        # ページネーション
        paginator = Paginator(conversions, per_page)
        page_obj = paginator.get_page(page)

        # レスポンス生成
        conversion_list = []
        for conversion in page_obj:
            generated_images = []
            for gen_img in conversion.generated_images.all():
                generated_images.append({
                    'id': gen_img.id,
                    'image_url': f"/media/{gen_img.image_path}",
                    'thumbnail_url': f"/media/{gen_img.image_path}",  # サムネイル未実装の場合は同じURL
                    'brightness_adjustment': gen_img.brightness_adjustment,
                    'expires_at': gen_img.expires_at.isoformat() if gen_img.expires_at else None,
                    'created_at': gen_img.created_at.isoformat()
                })

            conversion_list.append({
                'id': conversion.id,
                'original_image_url': f"/media/{conversion.original_image_path}",
                'original_image_name': conversion.original_image_name,
                'prompt': conversion.prompt,
                'model_name': conversion.model_name,
                'preset_id': conversion.preset_id,
                'preset_name': conversion.preset_name,
                'generation_count': conversion.generation_count,
                'aspect_ratio': conversion.aspect_ratio,
                'status': conversion.status,
                'processing_time': float(conversion.processing_time) if conversion.processing_time else None,
                'created_at': conversion.created_at.isoformat(),
                'generated_images': generated_images
            })

        return JsonResponse({
            'status': 'success',
            'conversions': conversion_list,
            'pagination': {
                'current_page': page_obj.number,
                'per_page': per_page,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count
            }
        })

    except ValueError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid page or per_page parameter'
        }, status=400)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'予期しないエラーが発生しました: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
@login_required_api
def gallery_detail(request, conversion_id):
    """
    変換詳細取得

    GET /api/v1/gallery/{conversion_id}/

    Response:
        {
            "status": "success",
            "conversion": {
                "id": 1,
                "original_image_url": "/media/uploads/1/abc.jpg",
                "original_image_name": "photo.jpg",
                "original_image_size": 1234567,
                "prompt": "プロフェッショナルな...",
                "generation_count": 3,
                "status": "completed",
                "processing_time": 12.345,
                "created_at": "2025-10-31T12:00:00Z",
                "generated_images": [...]
            }
        }
    """
    try:
        # 変換取得（権限チェック、キャンセル済み除外）
        conversion = ImageConversion.objects.select_related('user').prefetch_related(
            'generated_images'
        ).get(id=conversion_id, user=request.user, is_deleted=False)
        
        # キャンセルされた変換は404を返す
        if conversion.status == 'cancelled':
            return JsonResponse({
                'status': 'error',
                'message': '変換が見つかりません'
            }, status=404)

        # 生成画像一覧
        generated_images = []
        for gen_img in conversion.generated_images.filter(is_deleted=False):
            generated_images.append({
                'id': gen_img.id,
                'image_url': f"/media/{gen_img.image_path}",
                'image_name': gen_img.image_name,
                'image_size': gen_img.image_size,
                'brightness_adjustment': gen_img.brightness_adjustment,
                'expires_at': gen_img.expires_at.isoformat() if gen_img.expires_at else None,
                'created_at': gen_img.created_at.isoformat()
            })

        return JsonResponse({
            'status': 'success',
            'conversion': {
                'id': conversion.id,
                'original_image_url': f"/media/{conversion.original_image_path}",
                'original_image_name': conversion.original_image_name,
                'original_image_size': conversion.original_image_size,
                'prompt': conversion.prompt,
                'generation_count': conversion.generation_count,
                'aspect_ratio': conversion.aspect_ratio,
                'status': conversion.status,
                'processing_time': float(conversion.processing_time) if conversion.processing_time else None,
                'error_message': conversion.error_message,
                'created_at': conversion.created_at.isoformat(),
                'generated_images': generated_images
            }
        })

    except ImageConversion.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': '変換が見つかりません'
        }, status=404)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'予期しないエラーが発生しました: {str(e)}'
        }, status=500)


@require_http_methods(["DELETE"])
@login_required_api
def gallery_delete(request, conversion_id):
    """
    変換削除（論理削除）

    DELETE /api/v1/gallery/{conversion_id}/

    Response:
        {
            "status": "success",
            "message": "変換を削除しました"
        }
    """
    try:
        # 変換取得（権限チェック）
        conversion = ImageConversion.objects.get(
            id=conversion_id,
            user=request.user,
            is_deleted=False
        )

        # 論理削除
        conversion.is_deleted = True
        conversion.save()

        # 関連する生成画像も論理削除
        GeneratedImage.objects.filter(conversion=conversion).update(is_deleted=True)

        return JsonResponse({
            'status': 'success',
            'message': '変換を削除しました'
        })

    except ImageConversion.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': '変換が見つかりません'
        }, status=404)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'予期しないエラーが発生しました: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
@login_required_api
def image_detail(request, image_id):
    """
    生成画像詳細取得

    GET /api/v1/gallery/images/{image_id}/

    Response:
        {
            "status": "success",
            "image": {
                "id": 1,
                "image_url": "/media/generated/1/xyz.jpg",
                "image_name": "generated_001.jpg",
                "image_size": 234567,
                "brightness_adjustment": 0,
                "expires_at": "2025-11-30T12:00:00Z",
                "created_at": "2025-10-31T12:00:00Z",
                "conversion": {
                    "id": 1,
                    "original_image_url": "/media/uploads/1/abc.jpg",
                    "prompt": "..."
                }
            }
        }
    """
    try:
        # 画像取得（権限チェック、キャンセル済み変換の画像は除外）
        image = GeneratedImage.objects.select_related('conversion', 'conversion__user').get(
            id=image_id,
            conversion__user=request.user,
            conversion__is_deleted=False,
            conversion__status__in=['pending', 'processing', 'completed', 'failed'],  # cancelledを除外
            is_deleted=False
        )

        return JsonResponse({
            'status': 'success',
            'image': {
                'id': image.id,
                'image_url': f"/media/{image.image_path}",
                'image_name': image.image_name,
                'image_size': image.image_size,
                'brightness_adjustment': image.brightness_adjustment,
                'expires_at': image.expires_at.isoformat() if image.expires_at else None,
                'created_at': image.created_at.isoformat(),
                'conversion': {
                    'id': image.conversion.id,
                    'original_image_url': f"/media/{image.conversion.original_image_path}",
                    'aspect_ratio': image.conversion.aspect_ratio,
                    'prompt': image.conversion.prompt,
                    'model_name': image.conversion.model_name,
                    'preset_id': image.conversion.preset_id,
                    'preset_name': image.conversion.preset_name,
                }
            }
        })

    except GeneratedImage.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': '画像が見つかりません'
        }, status=404)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'予期しないエラーが発生しました: {str(e)}'
        }, status=500)


@require_http_methods(["DELETE"])
@login_required_api
def image_delete(request, image_id):
    """
    生成画像削除（論理削除）

    DELETE /api/v1/gallery/images/{image_id}/

    Response:
        {
            "status": "success",
            "message": "画像を削除しました"
        }
    """
    try:
        # 画像取得（権限チェック、キャンセル済み変換の画像は除外）
        image = GeneratedImage.objects.select_related('conversion').get(
            id=image_id,
            conversion__user=request.user,
            conversion__is_deleted=False,
            conversion__status__in=['pending', 'processing', 'completed', 'failed'],  # cancelledを除外
            is_deleted=False
        )

        # 論理削除
        image.is_deleted = True
        image.save()

        return JsonResponse({
            'status': 'success',
            'message': '画像を削除しました'
        })

    except GeneratedImage.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': '画像が見つかりません'
        }, status=404)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'予期しないエラーが発生しました: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
@login_required_api
def image_download(request, image_id):
    """
    生成画像ダウンロード

    GET /api/v1/gallery/images/{image_id}/download/

    Response:
        画像ファイル（Content-Disposition: attachment）
    """
    try:
        # 画像取得（権限チェック、キャンセル済み変換の画像は除外）
        image = GeneratedImage.objects.select_related('conversion').get(
            id=image_id,
            conversion__user=request.user,
            conversion__is_deleted=False,
            conversion__status__in=['pending', 'processing', 'completed', 'failed'],  # cancelledを除外
            is_deleted=False
        )

        # ファイルパス
        file_path = os.path.join(settings.MEDIA_ROOT, image.image_path)

        if not os.path.exists(file_path):
            raise Http404('ファイルが見つかりません')

        # ダウンロードファイル名生成
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        ext = os.path.splitext(image.image_name)[1]
        download_filename = f"generated_{timestamp}{ext}"

        # ファイルレスポンス
        response = FileResponse(open(file_path, 'rb'))
        response['Content-Disposition'] = f'attachment; filename="{download_filename}"'
        response['Content-Type'] = 'application/octet-stream'

        return response

    except GeneratedImage.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': '画像が見つかりません'
        }, status=404)

    except Http404:
        return JsonResponse({
            'status': 'error',
            'message': 'ファイルが見つかりません'
        }, status=404)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'予期しないエラーが発生しました: {str(e)}'
        }, status=500)


@require_http_methods(["PATCH"])
@login_required_api
def image_brightness(request, image_id):
    """
    画像輝度調整

    PATCH /api/v1/gallery/images/{image_id}/brightness/

    Request Body:
        {
            "adjustment": 10  // -50〜+50
        }

    Response:
        {
            "status": "success",
            "image": {
                "id": 1,
                "image_url": "/media/generated/1/xyz_brightness_+10.jpg",
                "brightness_adjustment": 10,
                "message": "輝度を調整しました"
            }
        }
    """
    try:
        # リクエストボディ取得
        data = json.loads(request.body)
        adjustment = data.get('adjustment')

        if adjustment is None:
            return JsonResponse({
                'status': 'error',
                'message': 'adjustmentパラメータが必要です'
            }, status=400)

        # 画像取得（権限チェック、キャンセル済み変換の画像は除外）
        image = GeneratedImage.objects.select_related('conversion').get(
            id=image_id,
            conversion__user=request.user,
            conversion__is_deleted=False,
            conversion__status__in=['pending', 'processing', 'completed', 'failed'],  # cancelledを除外
            is_deleted=False
        )

        base_image_path = BrightnessAdjustmentService.resolve_base_image_path(image.image_path)
        previous_adjusted_path = image.image_path if image.image_path != base_image_path else None

        if adjustment == 0:
            # 0の場合は元画像に戻す
            if previous_adjusted_path:
                BrightnessAdjustmentService.delete_adjusted_image(previous_adjusted_path)
            image.image_path = base_image_path
            image.image_name = os.path.basename(base_image_path)
            image.brightness_adjustment = 0
            base_full_path = Path(settings.MEDIA_ROOT) / base_image_path
            if base_full_path.exists():
                image.image_size = base_full_path.stat().st_size
            image.updated_at = timezone.now()
            image.save(update_fields=['image_path', 'image_name', 'image_size', 'brightness_adjustment', 'updated_at'])
        else:
            adjusted_image_path = BrightnessAdjustmentService.adjust_brightness(
                base_image_path,
                adjustment
            )

            if previous_adjusted_path and previous_adjusted_path != adjusted_image_path:
                BrightnessAdjustmentService.delete_adjusted_image(previous_adjusted_path)

            image.image_path = adjusted_image_path
            image.image_name = os.path.basename(adjusted_image_path)
            image.brightness_adjustment = adjustment
            adjusted_full_path = Path(settings.MEDIA_ROOT) / adjusted_image_path
            if adjusted_full_path.exists():
                image.image_size = adjusted_full_path.stat().st_size
            image.updated_at = timezone.now()
            image.save(update_fields=['image_path', 'image_name', 'image_size', 'brightness_adjustment', 'updated_at'])

        message = '輝度をリセットしました' if adjustment == 0 else '輝度を調整しました'

        return JsonResponse({
            'status': 'success',
            'image': {
                'id': image.id,
                'image_url': f"/media/{image.image_path}",
                'brightness_adjustment': image.brightness_adjustment,
                'message': message
            }
        })

    except GeneratedImage.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': '画像が見つかりません'
        }, status=404)

    except BrightnessAdjustmentError as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

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
