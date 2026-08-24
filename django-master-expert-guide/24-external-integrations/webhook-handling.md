# Webhook Handling in Django

## 1. Mental Model
```text
[External Service (Stripe)] --(POST /webhook/)--> [Django Webhook Endpoint]
                                                          |
                                                  (Verify Signature)
                                                          |
                                                  (Save to DB 'Event' table) -> HTTP 200 OK
                                                          |
                                                  (Trigger Celery Task)
                                                          |
                                                  [Process Event Async]
```
Webhooks are asynchronous events pushed to your application. They are fire-and-forget from the sender's perspective. Your goal is to securely accept them, acknowledge them quickly, and process them safely.

## 2. Why It Exists
Polling external APIs for updates is inefficient and rate-limited. Webhooks allow near real-time updates (e.g., "Payment Succeeded"). However, they introduce challenges: untrusted payloads, duplicate deliveries, and processing delays.

## 3. Internal Working
When a webhook hits Django, it goes through middleware and reaches your view. If your view processes the webhook synchronously (e.g., generating PDFs, querying other APIs) and takes more than a few seconds, the webhook provider might time out and retry the webhook, leading to duplicate processing.

## 4. Basic Implementation
```python
# 🔴 ANTI-PATTERN: Synchronous, unsafe webhook processing
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def stripe_webhook_bad(request):
    payload = json.loads(request.body)
    # No signature verification! Anyone can hit this endpoint.
    if payload['type'] == 'payment_intent.succeeded':
        # Processing synchronously! Could time out Stripe.
        process_payment(payload) 
    return HttpResponse(status=200)
```

## 5. Production-Ready Implementation
The **Ingest-First Pattern**:
```python
# ✅ PRODUCTION-READY
import hmac
import hashlib
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import WebhookEvent
from .tasks import process_webhook_task

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    # 1. Verify Signature
    if not verify_stripe_signature(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET):
        return HttpResponseForbidden("Invalid signature")
    
    # 2. Ingest First (Deduplication & Durability)
    import json
    event_dict = json.loads(payload)
    event_id = event_dict.get('id')
    
    # Use get_or_create to handle duplicate webhooks gracefully
    event_obj, created = WebhookEvent.objects.get_or_create(
        external_id=event_id,
        defaults={
            'provider': 'stripe',
            'payload': event_dict,
            'status': 'pending'
        }
    )
    
    # 3. Process Async
    if created or event_obj.status == 'failed':
        # transaction.on_commit ensures the task is only queued if the DB insert commits
        from django.db import transaction
        transaction.on_commit(lambda: process_webhook_task.delay(event_obj.id))
        
    # 4. Fast Acknowledge
    return HttpResponse(status=200)
    
def verify_stripe_signature(payload, sig_header, secret):
    # Implementation of Stripe's signature verification
    # ...
    return True
```

## 6. Anti-Patterns
🔴 **Trusting the payload:** Failing to verify HMAC signatures allows attackers to spoof payments.
🔴 **Synchronous processing:** Doing heavy work in the webhook view leads to timeouts and retries.
🔴 **Lack of idempotency:** Failing to handle the same webhook ID twice (most providers guarantee *at least once* delivery, meaning duplicates will happen).

## 7. Environment-Specific Behavior
| Environment | Behavior | Consideration |
|-------------|----------|---------------|
| Local | Cannot receive public webhooks | Use Stripe CLI or ngrok to tunnel traffic to localhost. |
| Production | High volume | Database MUST have unique index on `external_id` to prevent race conditions during deduplication. |

## 8. Local Development Issues
🔴 **SYMPTOM:** Webhook view throws 403 Forbidden locally.
🔍 **CAUSE:** The webhook payload is modified by a reverse proxy or ngrok, or you are testing with a payload generated with a different secret.
🔧 **FIX:** Ensure you capture raw `request.body` (do not access `request.POST` first, as it consumes the stream).

## 9. Production Issues
🔴 **INCIDENT:** Users credited multiple times for a single payment.
* **Severity:** Critical (Financial Loss)
* **Investigation:** Stripe sent the same webhook 3 times because the Django view took 15 seconds to respond (generating a receipt). Stripe timed out and retried. The view lacked idempotency checks.
* **Root Cause:** Synchronous processing + lack of idempotency.
* **Fix:** Implemented the Ingest-First pattern with `WebhookEvent` model and unique constraints on `stripe_event_id`.

## 10. Failure Simulation
Use a tool like `curl` to send the exact same webhook payload twice in rapid succession to test race conditions in your deduplication logic.

## 11. Decision Matrix
| Pattern | Pros | Cons |
|---------|------|------|
| Sync Processing | Simple to write | Brittle, scales poorly, timeout risks |
| Ingest-First DB | Robust, retryable, auditable | Requires DB table, Celery setup |
| Direct to Queue (Redis) | Extremely fast | Harder to audit, potential data loss |

## 12. Senior-Level Questions
**Q: Why must you read `request.body` instead of `request.POST` when verifying webhook signatures?**
A: Webhook providers sign the exact raw byte stream of the payload. If you access `request.POST`, Django parses the body and populates the QueryDict. If you then try to reconstruct the body from `request.POST`, the byte order, whitespace, or encoding might change slightly, causing the HMAC hash to mismatch the provider's signature. Always read `request.body` first.

## 13. Production Checklist
- [ ] CSRF exemption applied (`@csrf_exempt`).
- [ ] HMAC signature verified using raw `request.body`.
- [ ] Idempotency implemented (DB unique constraints on event ID).
- [ ] Fast return (HTTP 2xx) before processing.
- [ ] Async processing via Celery or similar.
