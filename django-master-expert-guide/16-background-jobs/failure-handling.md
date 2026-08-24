# Failure Handling in Celery: A Staff Engineer's Guide [DJANGO 6.1+]

## 1. Mental Model: Celery Failure States

Tasks fail. A robust system doesn't prevent failure; it routes and handles it gracefully.

```text
                      [Task Exception]
                             |
                             v
                  +--------------------+
                  |  Retry Policy?     |
                  +--------------------+
                   /                  \
             [YES]                     [NO or Max Retries]
               /                          \
+-------------------------+      +-------------------------+
| Exponential Backoff     |      | Dead Letter Queue (DLQ) |
| (countdown = 2^retries) |      | or Error Database Table |
+-------------------------+      +-------------------------+
               \                          /
                \--> [Message Broker] <--/
```

---

## 2. Why It Exists

Network requests drop. APIs rate-limit you. Databases deadlock. If you don't handle Celery exceptions, messages are lost forever, or worse, they infinitely loop and crash your workers (Poison Pill).

---

## 3. Basic Implementation vs. Production Implementation

### ❌ The Broken/Basic Way

```python
from celery import shared_task
import requests

@shared_task
def send_webhook(url, payload):
    # 🚨 DANGER 1: No timeout. 
    # 🚨 DANGER 2: No retry on 502/503.
    # 🚨 DANGER 3: Fails silently if an exception occurs.
    requests.post(url, json=payload)
```

### ✅ The Production-Hardened Way (Tenacity + Celery Retries)

```python
from celery import shared_task
from celery.exceptions import Reject
import httpx
import logging

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    max_retries=5,
    autoretry_for=(httpx.RequestError,),
    retry_backoff=True, # Uses exponential backoff
    retry_jitter=True,  # Prevents thundering herds on retry
    acks_late=True,     # Message stays in queue until SUCCESS
)
def send_webhook_safe(self, url, payload):
    try:
        # 🔧 FIX: Strict timeouts
        with httpx.Client(timeout=5.0) as client:
            response = client.post(url, json=payload)
            
            if response.status_code in [400, 401, 403, 404]:
                # 🔧 FIX: Do NOT retry client errors. It's a waste of CPU.
                logger.error(f"Client error {response.status_code} for {url}")
                # Rejecting removes it from queue without retrying
                raise Reject(f"Fatal client error: {response.status_code}")
                
            response.raise_for_status()
            
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in [429, 502, 503, 504]:
            logger.warning("Upstream rate limited or down. Retrying...")
            raise self.retry(exc=exc)
        raise Reject("Unhandled status error")
```

---

## 4. Production Incident: The Poison Pill

### 🔴 INCIDENT: All Celery Workers Stopped Processing
**Severity:** SEV-1
**Symptoms:** Queue size spiked to 100,000. Workers were consuming 100% CPU but completing 0 tasks.
**Investigation:** 
- Straced a worker process. It was stuck in a tight loop parsing a massive 500MB JSON payload.
- The task was configured with `acks_late=False` (default). 
**Root Cause:**
A malicious user uploaded a 500MB JSON file to an async processing endpoint. The worker pulled the task, crashed (OOM), and restarted. Because it crashed before completing, but *after* acknowledging (default behavior), the message was lost. Wait, no. We configured `acks_late=True` previously, so it went BACK to the queue. The next worker picked it up, crashed, returned to queue. Infinite death loop! (Poison Pill).
**🔧 FIX & Prevention:**
1. **Reject on Worker Lost**: Tell Celery not to retry if the worker dies mid-execution.
2. **Task Size Limits**: Reject payloads > 1MB at the API gateway.
```python
# settings.py
# If a worker is OOM killed, do not return the task to the queue.
CELERY_TASK_REJECT_ON_WORKER_LOST = True
```

---

## 5. Environment Matrix

| Feature | Dev | Prod |
| :--- | :--- | :--- |
| **Broker** | Redis (Drops messages on restart) | RabbitMQ (Persistent Disk) |
| **Acks Late** | False (faster) | True (safer) |
| **Error Tracking**| Console logs | Sentry Integration (`sentry_sdk.integrations.celery`) |
