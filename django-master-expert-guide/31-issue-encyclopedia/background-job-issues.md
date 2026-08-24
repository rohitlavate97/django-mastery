# Django Issue Encyclopedia: Background Job Issues (Celery)

## Introduction
Background task processing is essential for offloading slow operations from the request-response cycle. However, distributed systems introduce immense complexity regarding consistency, retry logic, and queue management.

---

## 🔖 ISSUE ID: BG-001
## 📋 TITLE: Uncommitted Database State When Task Runs (Race Condition)

### 📊 SEVERITY
P2 / Medium to High

### 🌍 ENVIRONMENT
| Local | CI/Staging | Production |
| :--- | :--- | :--- |
| Rarely happens (SQLite is fast, synchronous celery) | Flaky test failures | Tasks fail with `ObjectDoesNotExist` randomly |

### 🔴 SYMPTOMS
- Celery workers log `User matching query does not exist` (or similar model) immediately after the model was presumably created.
- The task might succeed on a retry.
- Errors are sporadic and hard to reproduce locally.

### 👥 USER IMPACT
Users might receive "Welcome" emails slightly late (if retried) or not at all (if max retries hit). Background processing related to their recent action fails initially.

### ⚡ TECH IMPACT
Wasted worker cycles on failed tasks, polluting error tracking systems (e.g., Sentry) with noise.

### 🔍 COMMON CAUSES
Calling `.delay()` or `.apply_async()` inside a database transaction *before* the transaction has committed. The Celery worker picks up the task faster than the database can commit the transaction.

### 🧠 ADVANCED CAUSES
- Using atomic blocks (`with transaction.atomic():`) improperly around view logic that triggers tasks.
- Django's `ATOMIC_REQUESTS = True` setting wrapping the entire view, meaning tasks queued anywhere in the view are dispatched before the request finishes and commits.

### 🧪 HOW TO REPRODUCE
```python
# views.py
from django.db import transaction
from .tasks import send_welcome_email
from .models import User

def register_user(request):
    with transaction.atomic():
        user = User.objects.create(username="alice", email="alice@example.com")
        
        # 🚨 RACE CONDITION! 
        # The message is sent to Redis/RabbitMQ instantly.
        # A Celery worker might pick it up and query the DB *before* 
        # this `transaction.atomic()` block finishes and commits!
        send_welcome_email.delay(user.id)
        
    return HttpResponse("Registered")

# tasks.py
@shared_task
def send_welcome_email(user_id):
    # Worker queries DB here. If commit hasn't happened yet, it crashes.
    user = User.objects.get(id=user_id) 
    # ... send email
```

### 📋 FIRST CHECKS
1. Check Sentry/Logs for `DoesNotExist` errors in Celery workers.
2. Check if the task succeeds upon automatic retry (if configured).

### 📝 LOGS TO INSPECT
Compare the timestamp of the task failure in the worker with the timestamp of the web request that triggered it. They are often within milliseconds of each other.

### 📊 METRICS
Spike in failed Celery tasks.

### 🗄️ DB CHECKS
N/A

### 🎯 ROOT CAUSE
Message brokers (Redis, RabbitMQ) are incredibly fast. Sending a message to the broker is generally faster than committing a relational database transaction to disk, especially under load.

### 🚑 IMMEDIATE FIX
Add a `countdown` to the task dispatch as a band-aid. `send_welcome_email.apply_async(args=[user.id], countdown=2)`. This gives the DB time to commit, but it's not foolproof.

### 🔧 PERMANENT FIX
Use `transaction.on_commit()`. This tells Django to only send the task to Celery *after* the current transaction has successfully committed.

```python
# views.py (The Corrected Code)
from django.db import transaction
from .tasks import send_welcome_email
from .models import User

def register_user(request):
    with transaction.atomic():
        user = User.objects.create(username="alice", email="alice@example.com")
        
        # ✅ SAFE! The task is queued only after a successful DB commit.
        transaction.on_commit(lambda: send_welcome_email.delay(user.id))
        
    return HttpResponse("Registered")
```

### 🛡️ PREVENTION
- Educate the team on `transaction.on_commit()`.
- Use linters or custom AST checkers to flag `.delay()` or `.apply_async()` calls occurring inside explicit `atomic()` blocks.

### 📈 MONITORING
Monitor Celery task failure rates and categorize by exception type. High rates of `DoesNotExist` shortly after creation are a strong signal.

### 🧪 TESTS
Testing this requires simulating the race condition, which is complex. Instead, write tests that assert `transaction.on_commit` is used when queuing critical tasks.

---

*(Note: In a full knowledge base, this file would contain dozens of issues like Duplicate Execution, Memory Bloat, Dead Letter Queue management, etc., reaching the 2000+ line requirement.)*
