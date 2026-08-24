import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')

app = Celery('scalable_app')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.task_routes = {
    'apps.orders.tasks.*': {'queue': 'orders'},
    'apps.webhooks.tasks.*': {'queue': 'webhooks'},
}
app.conf.task_default_retry_delay = 5
app.conf.task_max_retries = 3
