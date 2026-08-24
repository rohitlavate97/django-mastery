from celery import shared_task
from .models import WebhookEvent

@shared_task(bind=True, max_retries=3)
def process_webhook_event(self, event_id):
    try:
        event = WebhookEvent.objects.get(id=event_id)
        if event.status != 'PENDING':
            return "Already processed"
            
        # Simulate processing
        if event.payload.get('event') == 'payment_failed':
            raise ValueError("Payment failed simulation")
            
        event.status = 'PROCESSED'
        event.save()
        return f"Processed event {event_id}"
    except Exception as exc:
        event = WebhookEvent.objects.get(id=event_id)
        event.status = 'FAILED'
        event.save()
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
