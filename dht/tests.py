from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings

from dht import alerts
from dht.models import Alert

TEST_ALERTS = {
    'THRESHOLDS': {'temp': {'min': 15, 'max': 30}, 'hum': {'min': 40, 'max': 60}},
    'CONSECUTIVE': 3,
    'EMAIL_TO': ['test@example.com'],
    'EMAIL_FROM': 'dht11@example.com',
    'TELEGRAM_BOT_TOKEN': 'x',
    'TELEGRAM_CHAT_ID': '1',
}


@override_settings(ALERTS=TEST_ALERTS,
                   MAILERS={'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}})
@mock.patch.object(alerts, 'SEND_IN_BACKGROUND', False)
@mock.patch.object(alerts, 'send_telegram', return_value=True)
class AlertTests(TestCase):
    def post(self, temp, hum):
        r = self.client.post('/api/post', {'temp': temp, 'hum': hum})
        self.assertEqual(r.status_code, 201)

    def test_two_bad_readings_do_not_alert(self, tg):
        self.post(31, 50)
        self.post(32, 50)
        self.assertEqual(len(mail.outbox), 0)
        tg.assert_not_called()

    def test_repeats_on_each_new_abnormal_reading(self, tg):
        for t in (31, 32, 33, 34, 35):
            self.post(t, 50)
        self.assertEqual(len(mail.outbox), 3)  # initial alert, then one reminder per reading
        self.assertEqual(tg.call_count, 3)
        self.assertIn('Température trop élevée', mail.outbox[0].subject)
        self.assertIn('31°C, 32°C, 33°C', mail.outbox[0].body)
        self.assertIn('Rappel DHT11', mail.outbox[1].subject)
        self.assertEqual(Alert.objects.filter(resolved_at__isnull=True).count(), 1)

    def test_interrupted_streak_does_not_alert(self, tg):
        for t in (31, 32, 25, 31, 32):
            self.post(t, 50)
        self.assertEqual(len(mail.outbox), 0)

    def test_three_consecutive_normal_readings_resolve_alert(self, tg):
        for h in (35, 34, 33, 50, 35, 50, 50, 50):
            self.post(22, h)
        self.assertEqual(len(mail.outbox), 3)
        self.assertIn('Humidité trop basse', mail.outbox[0].subject)
        self.assertIn('Rappel DHT11', mail.outbox[1].subject)
        self.assertIn('revenue à la normale', mail.outbox[2].subject)
        self.assertEqual(Alert.objects.filter(resolved_at__isnull=False).count(), 1)

    def test_temp_and_humidity_alert_independently(self, tg):
        for _ in range(3):
            self.post(10, 70)
        subjects = sorted(m.subject for m in mail.outbox)
        self.assertEqual(len(subjects), 2)
        self.assertIn('Humidité trop élevée', subjects[0])
        self.assertIn('Température trop basse', subjects[1])

    def test_limits_themselves_are_normal(self, tg):
        for _ in range(3):
            self.post(15, 60)
            self.post(30, 40)
        self.assertEqual(len(mail.outbox), 0)
