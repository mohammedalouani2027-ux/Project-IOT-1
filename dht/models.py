from django.db import models

class Dht11(models.Model):
    temp = models.FloatField(null=True)
    hum = models.FloatField(null=True)
    dt = models.DateTimeField(auto_now_add=True,null=True)



class Alert(models.Model):
    """One abnormal episode: opened after N bad readings in a row, closed when values are normal again."""
    METRICS = [('temp', 'Temperature'), ('hum', 'Humidity')]
    KINDS = [('low', 'Too low'), ('high', 'Too high')]

    metric = models.CharField(max_length=10, choices=METRICS)
    kind = models.CharField(max_length=10, choices=KINDS)
    threshold = models.FloatField()
    value = models.FloatField(help_text='latest abnormal value when the alert was raised')
    started_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        state = 'resolved' if self.resolved_at else 'OPEN'
        return f'{self.get_metric_display()} {self.get_kind_display()} ({self.value}) - {state}'
