from __future__ import absolute_import, unicode_literals
import os, sys
from celery import Celery
from pathlib import Path

# sys.path.append( Path(__file__).resolve().parent.parent.parent)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

app = Celery('cygnus')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Discover tasks in all registered Django app configs.
# app.autodiscover_tasks()
app.autodiscover_tasks(['backend.services.celery_service'])


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
