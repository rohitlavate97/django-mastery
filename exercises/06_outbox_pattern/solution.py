import uuid
import json
from django.db import models, transaction
from django.utils import timezone

class OutboxEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    aggregate_type = models.CharField(max_length=255)
    aggregate_id = models.CharField(max_length=255)
    event_type = models.CharField(max_length=255)
    payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['processed', 'created_at']),
        ]

def publish_event(aggregate_type: str, aggregate_id: str, event_type: str, payload: dict):
    """
    Records an event in the outbox table as part of the current transaction.
    """
    OutboxEvent.objects.create(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        payload=payload
    )

class OutboxRelay:
    def __init__(self, publisher_callback):
        self.publisher_callback = publisher_callback

    def process_events(self, batch_size=100):
        """
        Reads unprocessed events, publishes them, and marks them as processed.
        Uses skip_locked=True for concurrency safety.
        """
        with transaction.atomic():
            events = OutboxEvent.objects.filter(
                processed=False
            ).select_for_update(
                skip_locked=True
            ).order_by('created_at')[:batch_size]

            for event in events:
                try:
                    self.publisher_callback(
                        event.aggregate_type,
                        event.aggregate_id,
                        event.event_type,
                        event.payload
                    )
                    event.processed = True
                    event.save(update_fields=['processed'])
                except Exception as e:
                    # In a real system, you might increment a retry count or use a dead letter queue
                    pass
