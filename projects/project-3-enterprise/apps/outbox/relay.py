import time
from django.utils import timezone
from .models import OutboxMessage
import structlog

logger = structlog.get_logger(__name__)

def process_outbox():
    # Fetch pending messages
    messages = OutboxMessage.objects.filter(status='PENDING').order_by('created_at')[:100]
    
    for msg in messages:
        try:
            # Simulate publishing to a message broker (Kafka, RabbitMQ, etc.)
            logger.info("Publishing message", event_type=msg.event_type, msg_id=str(msg.id))
            
            # Update status
            msg.status = 'PUBLISHED'
            msg.published_at = timezone.now()
            msg.save(update_fields=['status', 'published_at'])
            
        except Exception as e:
            logger.error("Failed to publish message", msg_id=str(msg.id), error=str(e))
            msg.status = 'FAILED'
            msg.save(update_fields=['status'])

if __name__ == '__main__':
    while True:
        process_outbox()
        time.sleep(2)
