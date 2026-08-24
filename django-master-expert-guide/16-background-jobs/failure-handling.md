# Failure Handling in Celery

## 1. Mental Model
```text
Task Fails -> Retry (Backoff + Jitter) -> Exceeds Max Retries -> Dead Letter Queue (DLQ)
Worker Crashes -> acks_late=True -> Message restored to Broker queue -> Picked up by another worker
```

## 2. Why It Exists
Network calls fail, APIs rate-limit, databases deadlock, and servers crash. Robust failure handling ensures data isn't lost and transient errors don't cause permanent failures.

## 3. Internal Working
When a task fails, Celery catches the exception. If `self.retry` is called, Celery calculates the delay, creates a new task message with incremented retries, and sends it to the broker. If `acks_late=True`, the worker only acknowledges the message to the broker *after* successful completion.

## 4. Basic Implementation
```python
@shared_task(bind=True, max_retries=3)
def fetch_data(self, url):
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise self.retry(exc=exc, countdown=5)
```

## 5. Production-Ready Implementation
```python
import random

@shared_task(
    bind=True, 
    max_retries=5, 
    acks_late=True, 
    reject_on_worker_lost=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def robust_api_call(self, data):
    # retry_backoff with jitter prevents thundering herd problem
    api_client.submit(data)
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:** `acks_late=False` (default) for critical tasks. If the worker is OOM killed mid-execution, the task is lost forever.
🔴 **Ticking Time Bomb:** Retrying without backoff or jitter, causing a DDoS on the downstream service when it recovers.

## 7. Environment-Specific Behavior
| Setting | RabbitMQ | Redis |
|---------|----------|-------|
| `acks_late` | Native support | Emulated via visibility timeout |
| DLQ | Native (x-dead-letter-exchange) | Manual implementation required |

## 8. Local Development Issues
🔴 SYMPTOM: Task runs multiple times.
🔍 CAUSE: Visibility timeout in Redis is too short; Redis gives the unacknowledged task to another worker.
🔧 FIX: Increase `broker_transport_options = {'visibility_timeout': 3600}`.

## 9. Production Issues
🚨 INCIDENT: Infinite Retry Loop
- **Investigation:** Task catches `Exception` and retries unconditionally, but `max_retries` was disabled or overridden incorrectly.
- **Fix:** Only retry on expected, transient exceptions. Let persistent exceptions (e.g., 404 Not Found, 400 Bad Request) fail immediately.

## 10. Failure Simulation
Hard kill a worker (`kill -9 <pid>`) while processing a long task with `acks_late=True`. Verify the task reappears in the queue and is processed by another worker.

## 11. Decision Matrix
- **acks_late=True:** Data correctness is critical (payments). Task MUST be idempotent!
- **acks_late=False:** Fire and forget (analytics pings).

## 12. Senior-Level Questions
**Q:** How do you implement a DLQ in Redis since it doesn't support it natively?
**A:** Use Celery's `task_failure` signal to catch exceptions and push the failed task details (args, kwargs, traceback) into a separate Redis list or a Django model for manual review.

## 13. Production Checklist
- [ ] `acks_late` evaluated for all tasks.
- [ ] Exponential backoff and jitter applied to retries.
- [ ] DLQ mechanism in place for max-retries exceeded.
- [ ] `visibility_timeout` configured correctly for Redis.
