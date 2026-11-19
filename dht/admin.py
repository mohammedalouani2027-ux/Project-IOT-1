from django.contrib import admin
from . import models

admin.site.register(models.Dht11)


@admin.register(models.Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('metric', 'kind', 'value', 'threshold', 'started_at', 'resolved_at')
    list_filter = ('metric', 'kind')
