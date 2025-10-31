"""
利用状況API
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone

from api.decorators import login_required_api
from images.models import ImageConversion


def _first_day(dt):
    """
    指定日時の月初を返す
    """
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _first_day_next_month(dt):
    """
    次月の月初を返す
    """
    if dt.month == 12:
        return dt.replace(year=dt.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return dt.replace(month=dt.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)


def _subtract_months(dt, months):
    """
    指定した月数分だけ過去の月初を取得
    """
    year = dt.year
    month = dt.month - months
    while month <= 0:
        month += 12
        year -= 1
    return dt.replace(year=year, month=month, day=1)


@require_http_methods(["GET"])
@login_required_api
def usage_summary(request):
    """
    現在の利用状況を返す
    """
    cache_key = f'usage_summary:{request.user.id}'
    cached = cache.get(cache_key)
    if cached:
        return JsonResponse({
            'status': 'success',
            'data': cached
        })

    profile = request.user.profile
    now = timezone.now()
    next_reset = _first_day_next_month(now)

    remaining = profile.remaining
    limit = profile.monthly_limit
    used = profile.monthly_used
    usage_percentage = (used / limit * 100) if limit else 0

    data = {
        'monthly_limit': limit,
        'monthly_used': used,
        'remaining': remaining,
        'usage_percentage': usage_percentage,
        'current_month': now.strftime('%Y-%m'),
        'reset_date': next_reset.isoformat(),
    }

    cache.set(cache_key, data, 300)

    return JsonResponse({
        'status': 'success',
        'data': data
    })


@require_http_methods(["GET"])
@login_required_api
def usage_history(request):
    """
    月次の利用履歴を返す
    """
    months_param = request.GET.get('months')
    if months_param is None:
        months = 6
    else:
        try:
            months = int(months_param)
        except (TypeError, ValueError):
            return JsonResponse({
                'status': 'error',
                'message': 'monthsは整数で指定してください'
            }, status=400)

    months = max(1, min(months, 12))

    cache_key = f'usage_history:{request.user.id}:{months}'
    cached = cache.get(cache_key)
    if cached:
        return JsonResponse({
            'status': 'success',
            'data': {
                'history': cached
            }
        })

    now = timezone.now()
    current_first = _first_day(now)
    start_boundary = _subtract_months(current_first, months - 1)

    conversions = ImageConversion.objects.filter(
        user=request.user,
        is_deleted=False,
        created_at__gte=start_boundary
    )

    aggregated = (
        conversions
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(
            conversion_count=Count('id'),
            used=Sum('generation_count'),
        )
    )

    aggregated_map = {}
    for item in aggregated:
        month_key = item['month'].strftime('%Y-%m')
        aggregated_map[month_key] = {
            'used': item['used'] or 0,
            'conversion_count': item['conversion_count'] or 0,
        }

    history = []
    profile = request.user.profile

    for offset in range(months):
        month_dt = _subtract_months(current_first, offset)
        month_key = month_dt.strftime('%Y-%m')
        stats = aggregated_map.get(month_key, {'used': 0, 'conversion_count': 0})
        history.append({
            'month': month_key,
            'limit': profile.monthly_limit,
            'used': stats['used'],
            'conversion_count': stats['conversion_count'],
        })

    cache.set(cache_key, history, 300)

    return JsonResponse({
        'status': 'success',
        'data': {
            'history': history
        }
    })
