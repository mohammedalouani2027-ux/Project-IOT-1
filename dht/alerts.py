"""Threshold alerts for DHT11 readings, sent by Gmail and Telegram.

Called after every new reading (see api.Dhtviews). For each metric:
  * if the last N readings (settings.ALERTS['CONSECUTIVE']) are ALL below the
    minimum, or ALL above the maximum, and no alert is open yet -> open an alert
    and notify;
  * while an alert is open, notify on every new reading that remains abnormal;
  * close it after N consecutive readings return inside the limits.
"""
import json
import logging
import threading
import urllib.error
import urllib.request

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Alert, Dht11

log = logging.getLogger(__name__)

LABELS = {'temp': ('Température', '°C'), 'hum': ('Humidité', '%')}

# set to False in tests so notifications are sent synchronously
SEND_IN_BACKGROUND = True


def _classify(value, limits):
    if value is None:
        return None
    if value < limits['min']:
        return 'low'
    if value > limits['max']:
        return 'high'
    return 'ok'


def check_alerts():
    cfg = settings.ALERTS
    n = cfg['CONSECUTIVE']
    recent = list(Dht11.objects.order_by('-dt', '-id')[:n])
    if not recent:
        return

    for metric, limits in cfg['THRESHOLDS'].items():
        states = [_classify(getattr(r, metric), limits) for r in recent]
        latest = states[0]
        open_alert = Alert.objects.filter(metric=metric, resolved_at__isnull=True).first()

        # Require a full normal streak before considering the incident resolved.
        if open_alert and latest == 'ok':
            if len(states) == n and all(s == 'ok' for s in states):
                open_alert.resolved_at = timezone.now()
                open_alert.save(update_fields=['resolved_at'])
                notify(_resolved_message(open_alert, getattr(recent[0], metric)))
            continue

        # Keep reminding for each new reading that remains on the alerted side.
        if open_alert and latest == open_alert.kind:
            notify(_reminder_message(open_alert, getattr(recent[0], metric)))
            continue

        # N abnormal readings in a row, all on the same side
        if len(states) == n and latest in ('low', 'high') and all(s == latest for s in states):
            if open_alert:  # jumped straight from too low to too high (or the reverse)
                open_alert.resolved_at = timezone.now()
                open_alert.save(update_fields=['resolved_at'])
            alert = Alert.objects.create(
                metric=metric,
                kind=latest,
                threshold=limits['min'] if latest == 'low' else limits['max'],
                value=getattr(recent[0], metric),
            )
            notify(_alert_message(alert, [getattr(r, metric) for r in reversed(recent)]))


# ---------- messages ----------

def _alert_message(alert, values):
    name, unit = LABELS[alert.metric]
    direction = 'trop basse' if alert.kind == 'low' else 'trop élevée'
    limit = 'minimum' if alert.kind == 'low' else 'maximum'
    vals = ', '.join(f'{v:g}{unit}' for v in values)
    subject = f'⚠️ Alerte DHT11 : {name} {direction} ({alert.value:g}{unit})'
    body = (
        f'{name} {direction} depuis {len(values)} mesures consécutives.\n'
        f'Dernières valeurs : {vals}\n'
        f'Seuil {limit} : {alert.threshold:g}{unit}\n'
        f'Heure : {timezone.localtime(alert.started_at):%d/%m/%Y %H:%M:%S}'
    )
    return subject, body


def _reminder_message(alert, value):
    name, unit = LABELS[alert.metric]
    direction = 'trop basse' if alert.kind == 'low' else 'trop élevée'
    limit = 'minimum' if alert.kind == 'low' else 'maximum'
    threshold = alert.threshold
    subject = f'⚠️ Rappel DHT11 : {name} toujours {direction} ({value:g}{unit})'
    body = (
        f'{name} est toujours {direction} : {value:g}{unit}\n'
        f'Seuil {limit} : {threshold:g}{unit}\n'
        f'Alerte ouverte depuis : {timezone.localtime(alert.started_at):%d/%m/%Y %H:%M:%S}\n'
        f'Heure : {timezone.localtime():%d/%m/%Y %H:%M:%S}'
    )
    return subject, body


def _resolved_message(alert, value):
    name, unit = LABELS[alert.metric]
    duration = alert.resolved_at - alert.started_at
    minutes = int(duration.total_seconds() // 60)
    subject = f'✅ DHT11 : {name} revenue à la normale ({value:g}{unit})'
    body = (
        f'{name} de nouveau dans les limites : {value:g}{unit}\n'
        f"Durée de l'alerte : {minutes // 60} h {minutes % 60} min\n"
        f'Heure : {timezone.localtime(alert.resolved_at):%d/%m/%Y %H:%M:%S}'
    )
    return subject, body


# ---------- sending ----------

def notify(message):
    """Send (subject, body) by email and Telegram, without slowing down the POST."""
    if SEND_IN_BACKGROUND:
        threading.Thread(target=_send_all, args=message, daemon=True).start()
    else:
        _send_all(*message)


def _send_all(subject, body):
    send_email(subject, body)
    send_telegram(f'{subject}\n\n{body}')


def send_email(subject, body):
    cfg = settings.ALERTS
    if not cfg['EMAIL_TO']:
        return False  # email alerts disabled (no GMAIL_USER / ALERT_EMAIL_TO in .env)
    try:
        send_mail(subject, body, cfg['EMAIL_FROM'], cfg['EMAIL_TO'])
        return True
    except Exception:
        log.exception('Alert email failed')
        return False


def send_telegram(text):
    cfg = settings.ALERTS
    token, chat_id = cfg['TELEGRAM_BOT_TOKEN'], cfg['TELEGRAM_CHAT_ID']
    if not token or not chat_id:
        log.warning('Telegram alert not sent: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing in .env')
        return False
    req = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/sendMessage',
        data=json.dumps({'chat_id': chat_id, 'text': text}).encode(),
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as e:
        # Telegram explains the problem in the response body, e.g. "chat not found"
        log.error('Telegram alert failed: %s %s', e.code, e.read().decode(errors='replace'))
        return False
    except Exception:
        log.exception('Telegram alert failed')
        return False
