import pytest
from apps.webhooks.models import WebhookEvent

@pytest.mark.django_db
def test_webhook_ingestion():
    event = WebhookEvent.objects.create(
        idempotency_key="test_123",
        payload={"event": "payment_succeeded"}
    )
    assert event.status == 'PENDING'
