from django.db import transaction
from .models import OutboxMessage

def publish_event(event_type: str, payload: dict):
    """
    Saves the event to the outbox table. Must be called within a transaction
    to guarantee atomicity with business data changes.
    """
    OutboxMessage.objects.create(
        event_type=event_type,
        payload=payload,
        status='PENDING'
    )
