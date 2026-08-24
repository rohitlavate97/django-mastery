# Celery Production Cheat Sheet for Django

## 1. Production Worker Startup Command

```bash
celery -A config worker \
    --loglevel=INFO \
    --concurrency=8 \
    --pool=prefork \
    --max-tasks-per-child=1000 \
    --max-memory-per-child=250000 \
    -Q default,high_priority,low_priority \
    --without-gossip \
    --without-mingle
```

---

## 2. Robust Task Definition Pattern

```python
from config.celery import app
import structlog

logger = structlog.get_logger(__name__)

@app.task(
    bind=True,
    name="orders.tasks.process_order_payment",
    max_retries=5,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_order_payment(self, order_id: str):
    try:
        # Business logic here
        pass
    except TransientGatewayError as exc:
        logger.warning("payment_gateway_retry", order_id=order_id, attempt=self.request.retries)
        raise self.retry(exc=exc)
    except PermanentValidationError as exc:
        logger.error("payment_validation_failed", order_id=order_id, error=str(exc))
        # Do not retry permanent errors
        raise
```

---

## 3. Transaction-Safe Task Dispatching

```python
from django.db import transaction
from orders.tasks import send_order_confirmation

def checkout_order(user, cart):
    with transaction.atomic():
        order = Order.objects.create(user=user, total=cart.total)
        # ... process items ...
        
        # NEVER call task.delay() directly in atomic block
        # ALWAYS use transaction.on_commit()
        transaction.on_commit(lambda: send_order_confirmation.delay(str(order.id)))
```

---

## 4. Key Production Settings (`settings.py`)

```python
CELERY_BROKER_URL = env("REDIS_URL", default="redis://redis:6379/1")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://redis:6379/2")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60       # Hard kill after 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 28 * 60  # Soft exception after 28 minutes
```
