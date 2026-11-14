import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "insighthub.settings")

app = Celery("insighthub")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
