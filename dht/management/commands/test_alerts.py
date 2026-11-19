"""Send a test message through Gmail and Telegram to check the .env configuration.

    python manage.py test_alerts
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from dht.alerts import send_email, send_telegram


class Command(BaseCommand):
    help = 'Send a test alert by email and Telegram.'

    def handle(self, *args, **opts):
        subject = '🔔 Test des alertes DHT11'
        body = 'Si vous lisez ceci, les alertes fonctionnent.'
        backend = settings.MAILERS['default']['BACKEND'].rsplit('.', 2)[-2]

        if not settings.ALERTS['EMAIL_TO']:
            self.stdout.write('Email: disabled (no GMAIL_USER in .env), skipped.')
        else:
            ok = send_email(subject, body)
            where = ', '.join(settings.ALERTS['EMAIL_TO'])
            if backend == 'console':
                self.stdout.write(self.style.WARNING(
                    'Email: Gmail password not set (.env), message printed above instead.'))
            else:
                self.stdout.write((self.style.SUCCESS if ok else self.style.ERROR)(
                    f'Email to {where}: {"sent" if ok else "FAILED (see error above)"}'))

        ok = send_telegram(f'{subject}\n\n{body}')
        self.stdout.write((self.style.SUCCESS if ok else self.style.ERROR)(
            f'Telegram: {"sent" if ok else "FAILED (check TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID in .env)"}'))
