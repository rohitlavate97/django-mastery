# Payment Integration in Django

## 1. Mental Model
```text
[User Checkout] -> [Django] -> (Create Payment Intent) -> [Stripe]
                      |
                 [Frontend JS] <- (Client Secret) -> [Stripe] (Collects Card securely)
                                                          |
                                                  (Webhook: Payment Succeeded)
                                                          |
                 [Django Webhook Handler] <---------------+
                      |
                 (Fulfill Order)
```
Payment integration is split into two phases: Intention (creating the charge intent) and Reconciliation (verifying via webhook that the charge actually succeeded). You must never trust the frontend to tell you a payment succeeded.

## 2. Why It Exists
Handling credit cards directly is a PCI compliance nightmare. Using gateways like Stripe or PayPal offloads the security burden. However, it introduces complex state management (Pending, Succeeded, Failed, Refunded) and the risk of double-charging users if race conditions aren't handled.

## 3. Internal Working
When you create a `PaymentIntent` in Stripe, Stripe reserves an ID and waits for the frontend to confirm the payment method. Once confirmed, Stripe executes the charge and fires a webhook. Django processes this webhook, looks up the corresponding Order, and transitions its state. 

## 4. Basic Implementation
```python
# 🔴 ANTI-PATTERN: Trusting the client
from django.http import JsonResponse
from .models import Order

def complete_checkout_bad(request):
    # Frontend says payment succeeded!
    order_id = request.POST.get('order_id')
    payment_status = request.POST.get('status')
    
    if payment_status == 'succeeded':
        order = Order.objects.get(id=order_id)
        order.status = 'paid'
        order.save()
        return JsonResponse({"status": "order fulfilled!"})
```
*Why it's bad:* A user can just send a POST request with `status=succeeded` and steal your products.

## 5. Production-Ready Implementation
```python
# ✅ PRODUCTION-READY
import stripe
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from .models import Order, Payment

stripe.api_key = settings.STRIPE_SECRET_KEY

def create_payment_intent(request, order_id):
    """Phase 1: Intention"""
    order = Order.objects.get(id=order_id)
    
    # Idempotency: Don't create a new intent if one exists
    if order.stripe_payment_intent_id:
        intent = stripe.PaymentIntent.retrieve(order.stripe_payment_intent_id)
    else:
        intent = stripe.PaymentIntent.create(
            amount=int(order.total_amount * 100), # Cents
            currency='usd',
            metadata={'order_id': order.id}
        )
        order.stripe_payment_intent_id = intent.id
        order.save(update_fields=['stripe_payment_intent_id'])
        
    return JsonResponse({'client_secret': intent.client_secret})

# Phase 2: Reconciliation (Webhook - See webhook-handling.md for robust wrapper)
@transaction.atomic
def process_payment_success(payment_intent_id):
    """
    Called strictly from the webhook handler.
    Uses select_for_update() to prevent double-fulfillment.
    """
    # Lock the order row until this transaction finishes
    order = Order.objects.select_for_update().get(stripe_payment_intent_id=payment_intent_id)
    
    if order.status == 'paid':
        # Already processed! Idempotent return.
        return
        
    # Create immutable payment record
    Payment.objects.create(
        order=order,
        stripe_id=payment_intent_id,
        amount=order.total_amount,
        status='succeeded'
    )
    
    order.status = 'paid'
    order.save(update_fields=['status'])
    # Trigger fulfillment (e.g., sending email, provisioning access)
```

## 6. Anti-Patterns
🔴 **Double Charge Risk:** Clicking "Submit" twice on the frontend creating two charges. Always use Idempotency Keys provided by Stripe (`Idempotency-Key` header) when creating resources.
🔴 **State Drift:** Order is "Paid" in Stripe, but "Pending" in Django because the webhook failed to process.

## 7. Environment-Specific Behavior
| Environment | Behavior | Consideration |
|-------------|----------|---------------|
| Local | Stripe Test Mode | Test webhooks via Stripe CLI. |
| CI | Mocked API | Use `responses` to mock Stripe API calls. |
| Production | Live Mode | Strict logging required. Never log raw CC data. |

## 8. Local Development Issues
🔴 **SYMPTOM:** Payment intent creation fails with "Invalid API Key".
🔍 **CAUSE:** You accidentally committed your secret key, Stripe revoked it, and now your local `.env` has a revoked key.
🔧 **FIX:** Roll keys in the Stripe dashboard and update `.env`. Use pre-commit hooks (like `trufflehog`) to prevent secrets from entering git.

## 9. Production Issues
🔴 **INCIDENT:** User paid, but order was never marked as paid.
* **Severity:** High (Customer Support nightmare)
* **Investigation:** The webhook was received and returned 200 OK. However, the `process_payment_success` function threw a `KeyError` because the Stripe metadata was missing an expected field. The task failed silently.
* **Root Cause:** Incomplete error handling in the async webhook task.
* **Fix:** Implemented a dead-letter queue (DLQ) for failed webhook processing tasks, and added a daily CRON job to reconcile "Pending" orders in Django with "Succeeded" intents in Stripe.

## 10. Failure Simulation
Open two tabs of your application and click "Pay" simultaneously for the same order. If you aren't using `select_for_update()`, you might fulfill the order twice or record duplicate payments.

## 11. Decision Matrix
| Strategy | Pros | Cons |
|----------|------|------|
| Stripe Checkout (Hosted) | Zero frontend code, highly secure | Less control over UI |
| Stripe Elements | Full UI control | Requires more frontend engineering |

## 12. Senior-Level Questions
**Q: How do you handle a scenario where the user pays on Stripe, but your database crashes before saving the `stripe_payment_intent_id` to the order?**
A: When you create the PaymentIntent, pass the Django `order_id` in the Stripe `metadata`. Even if Django crashes and loses track of the intent ID, the webhook will arrive with the `order_id` in the metadata, allowing you to link the successful payment back to the correct order.

## 13. Production Checklist
- [ ] `select_for_update()` used to lock order rows during fulfillment.
- [ ] Idempotency keys used for all Stripe mutating API calls.
- [ ] Metadata explicitly maps external Stripe objects to internal Django DB PKs.
- [ ] Automated reconciliation job runs nightly to catch missed webhooks.
