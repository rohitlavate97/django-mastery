import pytest
from apps.outbox.models import OutboxMessage
from apps.outbox.services import publish_event
from django.db import transaction

@pytest.mark.django_db
def test_outbox_publish_event():
    with transaction.atomic():
        publish_event("USER_CREATED", {"user_id": 1, "email": "test@example.com"})
        
    messages = OutboxMessage.objects.filter(status='PENDING')
    assert messages.count() == 1
    assert messages.first().event_type == "USER_CREATED"
