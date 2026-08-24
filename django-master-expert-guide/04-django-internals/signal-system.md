# Django Signal System

## 1. Mental Model
```text
Sender (Model.save()) --> Signal (post_save) --> Dispatcher --> Receiver Function(s)
```

## 2. Why It Exists
Signals allow decoupled applications get notified when actions occur elsewhere in the framework (e.g., a user is created, a model is saved).

## 3. Internal Working
Django signals use the Observer pattern. `Signal.send()` iterates over registered receivers. Registration uses `dispatch_uid` to prevent duplicates.

## 4. Basic Implementation
```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
```

## 5. Production-Ready Implementation
```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=User, dispatch_uid="create_user_profile_unique")
def create_profile(sender, instance, created, **kwargs):
    if created:
        # Use on_commit if triggering async Celery tasks
        transaction.on_commit(lambda: logger.info(f"User {instance.id} created & committed."))
        Profile.objects.get_or_create(user=instance)
```

## 6. Anti-Patterns
🔴 **TICKING TIME BOMB**: Business logic in signals.
```python
# INCORRECT: Implicit side effects making debugging a nightmare.
@receiver(post_save, sender=Order)
def charge_credit_card(sender, instance, **kwargs):
    # Firing an external API call inside a DB transaction!
    pass
```

## 7. Environment-Specific Behavior
Signals fire during testing too! Use `factory_boy` with `mute_signals()` to prevent unwanted side effects.

## 8. Local Development Issues
🔴 SYMPTOM: Signal fires multiple times.
🔍 CAUSE: App registry imported the signals module twice, and `dispatch_uid` was not provided.
🔧 FIX: Always use a unique string for `dispatch_uid` in `@receiver`.

## 9. Production Issues
INCIDENT: Celery task raised `ObjectDoesNotExist`.
SEVERITY: High
CAUSE: A `post_save` signal enqueued a Celery task with the object ID. The task started before the database transaction committed.
FIX: Wrap the Celery task dispatch in `transaction.on_commit()`.

## 10. Failure Simulation
```python
# Simulate signal failing silently
from django.dispatch import Signal
my_sig = Signal()

def failing_receiver(sender, **kwargs):
    raise ValueError("Crash")

my_sig.connect(failing_receiver)
# send_robust catches the exception and returns it as a tuple
responses = my_sig.send_robust(sender=None)
```

## 11. Decision Matrix
| Task | Use Signal? | Alternative |
|------|-------------|-------------|
| Audit logging | ✅ Yes | - |
| Cache invalidation | ✅ Yes | - |
| Core business logic | ❌ No | Explicit function call |

## 12. Senior-Level Questions
**Q: Do signals execute asynchronously?**
A: NO. Django signals are 100% synchronous and block the main thread. If a signal does a slow API call, the HTTP response is delayed.

## 13. Production Checklist
- [ ] All signals have `dispatch_uid`.
- [ ] No external API calls inside signals (use `on_commit` + Celery).
- [ ] Signals are imported in `AppConfig.ready()`.
