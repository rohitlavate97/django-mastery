# Celery Architecture with Django

## 1. Mental Model
```text
[ Django App ] --> (Message Broker) --> [ Celery Worker ] --> (Result Backend)
                       |                      |
                 Redis / RabbitMQ        PostgreSQL / Redis
```
Celery is a distributed task queue. It decouples long-running operations from the synchronous HTTP request-response cycle.

## 2. Why It Exists
HTTP requests must return quickly (typically <200ms) to prevent blocking WSGI/ASGI workers. Background tasks like sending emails, processing images, or calling external APIs can take seconds or minutes. Celery provides the infrastructure to run these tasks asynchronously.

## 3. Internal Working (Django Integration)
When you call `task.delay()`, Celery serializes the task arguments (usually JSON) and sends a message to the broker. 
Worker nodes continuously poll the broker. When a worker receives a message, it deserializes the payload, executes the task function, and stores the return value in the result backend.

```python
# Django internal trace approximation
def delay(self, *args, **kwargs):
    return self.apply_async(args, kwargs)

def apply_async(self, args=None, kwargs=None, **options):
    # 1. Serialize arguments
    # 2. Build task message
    # 3. Publish to broker via Kombu
    ...
```

## 4. Basic Implementation
```python
# celery.py
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
app = Celery('myproject')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# tasks.py
from celery import shared_task

@shared_task
def send_welcome_email(user_id):
    # Implementation
    pass
```

## 5. Production-Ready Implementation
```python
# settings.py
CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/1'
CELERY_TASK_ROUTES = {
    'emails.tasks.*': {'queue': 'emails'},
    'reports.tasks.*': {'queue': 'reports'},
}
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = 300 # Kill task after 5 minutes
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:** Passing complex objects (like Django model instances) to tasks.
```python
# BAD
@shared_task
def process_user(user_instance): ... 

# GOOD
@shared_task
def process_user(user_id):
    user = User.objects.get(id=user_id)
```

## 7. Environment-Specific Behavior
| Environment | Broker | Concurrency | Logging |
|-------------|--------|-------------|---------|
| Local | Redis/Memory | Solo/Prefork | Console |
| Docker | Redis | Prefork | stdout |
| Prod | RabbitMQ/Redis| Gevent/Prefork| JSON/ELK |

## 8. Local Development Issues
🔴 SYMPTOM: Tasks not executing.
🔍 CAUSE: Worker not running or using wrong broker DB.
🔧 FIX: Run `celery -A project worker -l INFO` and verify `CELERY_BROKER_URL`.

## 9. Production Issues
🚨 INCIDENT: Worker OOM (Out of Memory)
- **Investigation:** Celery workers leak memory over time due to Python's memory management and complex tasks.
- **Fix:** Set `CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000` and `CELERY_WORKER_MAX_MEMORY_PER_CHILD = 200000`.

## 10. Failure Simulation
To simulate broker failure, pause the Redis container: `docker pause redis`. Watch Celery workers throw connection errors.

## 11. Decision Matrix
- **RabbitMQ:** Complex routing, guarantees, high reliability.
- **Redis:** Simpler, faster, but less reliable in edge cases (visibility timeouts).
- **SQS:** Managed, scales infinitely, but higher latency.

## 12. Senior-Level Questions
**Q:** How do you ensure tasks don't run before the database transaction commits?
**A:** Use `transaction.on_commit(lambda: task.delay())`.

## 13. Production Checklist
- [ ] Task routing configured.
- [ ] `acks_late=True` for idempotent tasks.
- [ ] Timeouts set for all tasks.
- [ ] Concurrency model chosen appropriately (I/O bound vs CPU bound).
- [ ] Monitoring via Flower or Prometheus set up.
