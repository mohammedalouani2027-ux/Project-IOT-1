import csv

from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from .models import Dht11
from .periods import filter_period

# metric key in the URL -> (model field, display name, unit)
METRICS = {
    'temp': ('temp', 'Temperature', '°C'),
    'hum': ('hum', 'Humidity', '%'),
}


def test(request):
    return HttpResponse('jaouad laghmiri / mohammed alouani')


def dashboard(request):
    return render(request, 'dht/dashboard.html')


def graph(request, metric):
    if metric not in METRICS:
        raise Http404('Unknown metric')
    field, name, unit = METRICS[metric]
    return render(request, 'dht/graph.html', {
        'metric': metric, 'field': field, 'name': name, 'unit': unit,
    })


def export_csv(request, metric):
    if metric not in METRICS:
        raise Http404('Unknown metric')
    field, name, unit = METRICS[metric]

    try:
        qs, has_period = filter_period(Dht11.objects.all(), request)
    except ValueError:
        return HttpResponse('Invalid start/end date', status=400)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    stamp = timezone.localtime().strftime('%Y%m%d-%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="{metric}-{stamp}.csv"'
    response.write('\ufeff')  # BOM so Excel reads the ° sign correctly

    writer = csv.writer(response)
    writer.writerow(['datetime', f'{name} ({unit})'])
    for dt, value in qs.order_by('dt').values_list('dt', field):
        writer.writerow([timezone.localtime(dt).strftime('%Y-%m-%d %H:%M:%S') if dt else '', value])
    return response
