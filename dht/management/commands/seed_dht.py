"""Fill the database with fake DHT11 readings in the past, for testing the dashboard.

    python manage.py seed_dht                # 14 days, one reading every 5 minutes
    python manage.py seed_dht --days 30 --every 10
    python manage.py seed_dht --undo         # delete the readings added by the last seed

`dt` is auto_now_add, so readings can't be back-dated through the POST API;
this command inserts them and then rewrites their timestamps.
"""
import json
import math
import random
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from dht.models import Dht11

IDS_FILE = Path(settings.BASE_DIR) / '.seed_dht_ids.json'


class Command(BaseCommand):
    help = 'Insert fake back-dated DHT11 readings (or remove them with --undo).'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=14, help='how many days back (default 14)')
        parser.add_argument('--every', type=int, default=5, help='minutes between readings (default 5)')
        parser.add_argument('--gap-hours', type=int, default=6,
                            help='simulate the sensor being off for this long, 3 days ago (0 = no gap)')
        parser.add_argument('--undo', action='store_true', help='delete the readings from the last seed')

    def handle(self, *args, **opts):
        if opts['undo']:
            return self.undo()

        now = timezone.now()
        start = now - timedelta(days=opts['days'])
        step = timedelta(minutes=opts['every'])
        gap_start = now - timedelta(days=3)
        gap_end = gap_start + timedelta(hours=opts['gap_hours'])

        stamps, t = [], start
        while t < now:
            if not (gap_start <= t < gap_end):
                stamps.append(t)
            t += step

        rows = []
        for t in stamps:
            local = timezone.localtime(t)
            hour = local.hour + local.minute / 60
            day_wave = math.sin((hour - 9) / 24 * 2 * math.pi)   # warmest mid-afternoon
            drift = 1.5 * math.sin(t.timestamp() / 86400 / 4)   # slow multi-day drift
            temp = 22 + 3.5 * day_wave + drift + random.gauss(0, 0.3)
            hum = 52 - 8 * day_wave - 2 * drift + random.gauss(0, 1.0)
            rows.append(Dht11(temp=round(temp, 1), hum=round(max(0, min(100, hum)), 1)))

        with transaction.atomic():
            created = Dht11.objects.bulk_create(rows)
            ids = [r.id for r in created]
            if None in ids:  # backend didn't return ids: fetch the newest ones
                ids = list(Dht11.objects.order_by('-id').values_list('id', flat=True)[:len(rows)])[::-1]
            objs = list(Dht11.objects.filter(id__in=ids).order_by('id'))
            for obj, t in zip(objs, stamps):
                obj.dt = t
            Dht11.objects.bulk_update(objs, ['dt'], batch_size=500)

        previous = json.loads(IDS_FILE.read_text()) if IDS_FILE.exists() else []
        IDS_FILE.write_text(json.dumps(previous + ids))
        self.stdout.write(self.style.SUCCESS(
            f'Added {len(ids)} readings from {timezone.localtime(start):%d/%m/%Y %H:%M} '
            f'to now (gap of {opts["gap_hours"]} h around {timezone.localtime(gap_start):%d/%m %H:%M}).'))

    def undo(self):
        if not IDS_FILE.exists():
            self.stdout.write('Nothing to undo.')
            return
        ids = json.loads(IDS_FILE.read_text())
        deleted, _ = Dht11.objects.filter(id__in=ids).delete()
        IDS_FILE.unlink()
        self.stdout.write(self.style.SUCCESS(f'Deleted {deleted} seeded readings.'))
