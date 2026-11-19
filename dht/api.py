from .models import Dht11
from .serializers import DHT11serialize
from .periods import filter_period
from .alerts import check_alerts
from rest_framework.decorators import api_view
from rest_framework import status, generics
from rest_framework.response import Response
from django.core.mail import send_mail
from django.conf import settings
import rest_framework
@api_view(['GET'])
def Dlist(request):
    all_data = Dht11.objects.all()
    data = DHT11serialize(all_data, many=True).data
    return Response({'data': data})

class Dhtviews(generics.CreateAPIView):

    queryset = Dht11.objects.all()
    serializer_class = DHT11serialize

    def perform_create(self, serializer):
        serializer.save()
        check_alerts()

@api_view(['GET'])
def Dlatest(request):
    last = Dht11.objects.order_by('-dt').first()
    if last is None:
        return Response({'data': None})
    return Response({'data': DHT11serialize(last).data})


MAX_POINTS = 2000  # above this, readings are thinned out evenly so the chart stays fast


@api_view(['GET'])
def Dhistory(request):
    """Readings oldest -> newest for charting.

    ?start=&end=  ISO datetimes: every reading in that period (thinned to MAX_POINTS)
    otherwise     the last ?n= readings (default 50)
    """
    try:
        qs, has_period = filter_period(Dht11.objects.all(), request)
    except ValueError:
        return Response({'error': 'invalid start/end'}, status=status.HTTP_400_BAD_REQUEST)

    if has_period:
        rows = list(qs.order_by('dt'))
        total = len(rows)
        if total > MAX_POINTS:
            step = total / MAX_POINTS
            rows = [rows[int(i * step)] for i in range(MAX_POINTS)] + [rows[-1]]
    else:
        try:
            n = max(1, min(int(request.GET.get('n', 50)), MAX_POINTS))
        except ValueError:
            n = 50
        rows = list(qs.order_by('-dt')[:n])[::-1]
        total = len(rows)
    return Response({'data': DHT11serialize(rows, many=True).data, 'total': total})
