# Django Celery Architecture: A Staff Engineer's Guide [DJANGO 6.1+]

## 1. Mental Model: Celery & Broker Architecture

To truly master background tasks, you must visualize the precise flow of messages and state between Django, the Broker (e.g., Redis/RabbitMQ), and the Celery Workers. 

```text
                        +-----------------------------------------------+
                        | 3. Acknowledgment (ACK/NACK)                  |
                        v                                               |
+---------------+     +------------------+      +-------------------+   |
|               |     |                  | 1    |                   |   |
| Django Web    |---->| Message Broker   |----->| Celery Worker     |---+
| Process (WSGI)| 2   | (Redis/RabbitMQ) |      | (Prefetch Q)      |
|               |     |                  |      |                   |
+---------------+     +------------------+      +-------------------+
        |                     |                           |
        |                     |                           |
        | 4. Write State      |                           | 5. Update State
        v                     v                           v
+---------------------------------------------------------------+
|                      Result Backend (Redis/PG)                |
+---------------------------------------------------------------+
```

### Components Detailed
- **Django Process**: Serializes the task `delay()` call into JSON and pushes to a broker queue.
- **Message Broker**: Persists the message. If using RabbitMQ, it supports DLQs (Dead Letter Queues) natively.
- **Worker Prefetch**: Workers pull `worker_prefetch_multiplier * concurrency` messages at once.
- **Result Backend**: Where `Task.AsyncResult.state` is written.

---

## 2. Why It Exists (The Physics of Web Requests)

Django executes synchronously (WSGI) or asynchronously (ASGI). Even in ASGI, blocking I/O (like a 5-second API call or complex PDF generation) will stall the worker loop or thread pool. Background jobs decouple the HTTP response from the computational work.

---

## 3. Internal Working: Tracing `delay()`

When you call `my_task.delay(user_id=1)`, what actually happens in the Celery source code?

1. **`celery.app.task.Task.delay`** is a syntactic sugar wrapper for `apply_async`.
2. **`apply_async`** builds the message payload (kwargs, args, task ID, retries).
3. **`Kombu`** (Celery's messaging library) handles the actual routing. It checks the exchange and routing key.
4. **Serialization**: The payload is serialized (default JSON) and compressed (if configured).
5. **Transport**: The Kombu transport (e.g., `redis://` or `amqp://`) issues an `LPUSH` (Redis) or `basic_publish` (RabbitMQ).

---

## 4. Basic Implementation vs. Production Implementation

### ❌ The Broken/Basic Way (Ticking Time Bomb)

```python
# tasks.py
from celery import shared_task
from django.core.mail import send_mail
from .models import Report

@shared_task
def generate_and_send_report(report_id):
    # 🚨 DANGER 1: What if report_id doesn't exist yet due to DB transaction delay?
    report = Report.objects.get(id=report_id) 
    
    # 🚨 DANGER 2: No timeouts on long-running processes
    data = generate_pdf(report) 
    
    # 🚨 DANGER 3: No retry logic for transient network failures
    send_mail('Your Report', 'Here it is', 'from@example.com', [report.user.email])
```

### ✅ The Production-Hardened Way

```python
# tasks.py
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db import transaction
from django.core.mail import send_mail
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

logger = logging.getLogger(__name__)

@shared_task(
    bind=True, 
    max_retries=3,
    soft_time_limit=120,  # 🔧 FIX: Prevent hung tasks
    time_limit=130,       # Hard kill after 130s
    acks_late=True,       # 🔧 FIX: Acknowledge only AFTER completion
    reject_on_worker_lost=True
)
def generate_and_send_report_safe(self, report_id):
    try:
        # 🔧 FIX: Use select_related/prefetch_related if needed, handle DoesNotExist
        from .models import Report
        report = Report.objects.select_related('user').get(id=report_id)
        
        # Track start
        logger.info(f"Starting report generation for {report_id}")
        
        data = generate_pdf(report)
        
        # 🔧 FIX: Robust retry logic for external I/O
        send_email_with_retry(report.user.email, data)
        
        logger.info(f"Successfully completed {report_id}")
        return True
        
    except Report.DoesNotExist:
        logger.error(f"Report {report_id} not found. Dropping task.")
        # Do not retry if the record doesn't exist
        return False
    except SoftTimeLimitExceeded:
        logger.error(f"Task {self.request.id} exceeded soft time limit. Cleaning up...")
        # Clean up resources before the hard kill
        return False
    except Exception as exc:
        logger.exception(f"Unexpected error in {report_id}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def send_email_with_retry(email, data):
    send_mail('Your Report', 'Here it is', 'from@example.com', [email])

# In your views.py:
def trigger_report(request):
    report = Report.objects.create(user=request.user)
    # 🔧 FIX: transaction.on_commit ensures the record exists in the DB 
    # BEFORE the task is sent to the broker.
    transaction.on_commit(lambda: generate_and_send_report_safe.delay(report.id))
    return HttpResponse("Report started!")
```

---

## 5. Production Incident: The Broker Memory Saturation

### 🔴 INCIDENT: Redis OOM (Out of Memory) Crash
**Severity:** SEV-1
**Symptoms:** Celery workers stopped processing. Redis crashed. Django started returning 500s because the Redis connection timed out when calling `.delay()`.
**Investigation:** 
- `redis-cli info memory` showed memory was at 100%.
- We inspected the keyspace: `redis-cli --bigkeys`
- Found millions of keys prefixed with `celery-task-meta-*`.
**Root Cause:**
We enabled a Result Backend, but we were ignoring the results of 99% of our tasks. We also hadn't configured `CELERY_RESULT_EXPIRES`. The results accumulated infinitely.
**🔧 FIX & Prevention:**
```python
# settings.py
# 1. Ignore results globally unless explicitly requested
CELERY_TASK_IGNORE_RESULT = True

# 2. Set a short expiration for the ones we do keep
CELERY_RESULT_EXPIRES = 3600  # 1 hour

# 3. For tasks where you DO need results, override per task:
@shared_task(ignore_result=False)
def task_that_needs_result():
    pass
```

---

## 6. Environment Comparison Matrix

| Feature | Local (Docker) | CI (Pytest) | Staging | Production |
| :--- | :--- | :--- | :--- | :--- |
| **Broker** | Redis Container | Memory (`task_always_eager=True`) | Small Redis (1GB) | AWS ElastiCache / RabbitMQ Cluster |
| **Workers** | 1 worker, loglevel=DEBUG | Eager execution (no worker) | 2 workers | Auto-scaling ASG based on Queue length |
| **Prefetch** | Default (4) | N/A | Default (4) | Tuned (1 for long IO, 10 for fast CPU) |
| **Monitoring**| Flower | Pytest logs | Datadog/Sentry | Datadog + PagerDuty + Prometheus |

---

## 7. Pytest Test Suite for Celery

```python
# test_tasks.py
import pytest
from unittest.mock import patch
from celery.exceptions import Retry
from myapp.tasks import generate_and_send_report_safe
from myapp.models import Report

@pytest.mark.django_db
class TestReportTask:
    
    def test_task_skips_if_no_report(self, caplog):
        # Should gracefully fail and log
        result = generate_and_send_report_safe(9999)
        assert result is False
        assert "Report 9999 not found" in caplog.text

    @patch('myapp.tasks.send_email_with_retry')
    @patch('myapp.tasks.generate_pdf')
    def test_task_success(self, mock_pdf, mock_email):
        report = Report.objects.create(user_id=1)
        mock_pdf.return_value = b'pdfdata'
        
        result = generate_and_send_report_safe(report.id)
        
        assert result is True
        mock_email.assert_called_once_with(report.user.email, b'pdfdata')

    @patch('myapp.tasks.generate_pdf', side_effect=Exception("API Down"))
    def test_task_retries_on_failure(self):
        report = Report.objects.create(user_id=1)
        
        with pytest.raises(Retry):
            generate_and_send_report_safe(report.id)
```

## 8. Decision Matrix: Redis vs RabbitMQ

| Criteria | Redis | RabbitMQ |
| :--- | :--- | :--- |
| **Message Loss Tolerance** | Moderate (Pub/Sub can drop, lists are okay) | Zero (ACks and Disk persistence are rock solid) |
| **Visibility Timeout** | Handled manually by Celery, can be flaky | Native. Best in class. |
| **Setup Complexity** | Very Low | Moderate to High |
| **Dead Letter Queues (DLQ)**| Simulated via Celery config | Native routing |

*Staff Engineer Verdict:* Use Redis to start. When you hit 1,000+ msgs/sec or require strict financial-grade message guarantees and DLQs, migrate to RabbitMQ.
