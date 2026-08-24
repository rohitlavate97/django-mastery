# Django Signal System Internals [DJANGO 6.1+]

## 1. Mental Model
```text
[Sender (e.g. Model.save())]
       |
       v
signal.send(sender, **kwargs)
       |
       v
[Signal Dispatcher] -> Checks `receivers` list
       |
       v
   (Iterates registered functions)
   -> receiver_1(sender, **kwargs)
   -> receiver_2(sender, **kwargs)
```

## 2. Why It Exists
Allows decoupled applications get notified when actions occur elsewhere in the framework (Publish-Subscribe pattern). Example: Clearing cache when a model is saved without modifying the model's `save()` method.

## 3. Internal Working
Trace of `django/dispatch/dispatcher.py`:
```python
class Signal:
    def __init__(self):
        self.receivers = []
        self.lock = threading.Lock()

    def connect(self, receiver, sender=None, weak=True, dispatch_uid=None):
        # Uses weak references by default to prevent memory leaks
        lookup_key = (dispatch_uid, _make_id(sender))
        self.receivers.append((lookup_key, receiver))

    def send(self, sender, **named):
        responses = []
        if not self.receivers:
            return responses
            
        for receiver in self._live_receivers(sender):
            response = receiver(signal=self, sender=sender, **named)
            responses.append((receiver, response))
        return responses
```

## 4. Basic Implementation
```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User

@receiver(post_save, sender=User)
def user_saved(sender, instance, created, **kwargs):
    if created:
        print(f"Welcome {instance.username}!")
```

## 5. Production-Ready Implementation
```python
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order
from .tasks import send_order_confirmation_email

logger = logging.getLogger(__name__)

# ALWAYS use dispatch_uid to prevent duplicate registration
@receiver(post_save, sender=Order, dispatch_uid="order_post_save_email")
def trigger_order_email(sender, instance, created, **kwargs):
    try:
        if created and instance.status == 'paid':
            # Do NOT block the request/db transaction. Send to Celery.
            send_order_confirmation_email.delay(instance.id)
    except Exception as e:
        logger.error(f"Failed to trigger email for order {instance.id}: {e}")
```

## 6. Anti-Patterns
🔴 **TICKING TIME BOMB**: Mutating the instance inside `post_save` and calling `save()` again.
```python
@receiver(post_save, sender=User)
def infinite_loop(sender, instance, **kwargs):
    instance.is_active = True
    instance.save() # TRIGGERS POST_SAVE AGAIN! MAXIMUM RECURSION DEPTH!
```

## 7. Environment-Specific Behavior
Signals run synchronously in the same thread and database transaction context as the caller. If a signal crashes, it crashes the entire request!

## 8. Local Development Issues
🔴 SYMPTOM: Signal fires twice!
🔍 CAUSE: The module containing the signal was imported twice, registering the function twice.
🔧 FIX: Always use a unique `dispatch_uid` in the `@receiver` decorator.

## 9. Production Issues
INCIDENT: API Latency Spikes on `POST /orders`.
SEVERITY: High
CAUSE: A `post_save` signal was added to `Order` that made a synchronous HTTP call to an external CRM. When the CRM got slow, saving orders in Django hung.
FIX: Move the HTTP call to a background task (Celery). Signals should ONLY enqueue tasks or update caches.

## 10. Failure Simulation
```python
import pytest
from django.core.signals import request_finished

def test_signal_execution():
    flag = False
    def my_handler(sender, **kwargs):
        nonlocal flag
        flag = True
        
    request_finished.connect(my_handler)
    request_finished.send(sender=None)
    assert flag
```

## 11. Decision Matrix
| Requirement | Use Signals? | Alternative |
|-------------|--------------|-------------|
| Same app, tight coupling | ❌ No | Override `save()` method |
| Cross-app decoupling | ✅ Yes | N/A |
| Async processing needed | ❌ No | Celery / Background tasks |

## 12. Senior-Level Questions
**Q: What happens if a DB transaction rolls back, but your signal sent an email?**
A: The user gets an email, but the DB row doesn't exist! Use `transaction.on_commit(lambda: send_email.delay(id))` inside the signal to ensure it only runs if the DB commits successfully.

## 13. Production Checklist
- [ ] `dispatch_uid` used on all receivers.
- [ ] Heavy I/O is offloaded to Celery.
- [ ] `transaction.on_commit` used for irreversible actions (emails, external APIs).
