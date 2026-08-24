from django.urls import path
from .views import WebhookIngestView

urlpatterns = [
    path('', WebhookIngestView.as_view(), name='webhook-ingest'),
]
