from django.utils import timezone
from django.utils.dateparse import parse_datetime


def _parse(value):
    """Parse an ISO datetime from the query string; return an aware datetime or None."""
    if not value:
        return None
    dt = parse_datetime(value.replace(' ', '+'))  # '+' in a URL may arrive as a space
    if dt is None:
        raise ValueError(value)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


def filter_period(queryset, request):
    """Apply ?start=...&end=... (ISO datetimes) to a Dht11 queryset.

    Returns (queryset, has_period). Raises ValueError on a bad date.
    """
    start = _parse(request.GET.get('start'))
    end = _parse(request.GET.get('end'))
    if start and end and start > end:
        raise ValueError('start is after end')
    if start:
        queryset = queryset.filter(dt__gte=start)
    if end:
        queryset = queryset.filter(dt__lte=end)
    return queryset, bool(start or end)
