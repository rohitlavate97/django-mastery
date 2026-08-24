# Django Native Tasks & Async Primitives

## 1. Mental Model
```text
Old Way (External Queue):
Django -> Redis -> Celery Worker -> DB

New Way (Async Primitives + DB Queues):
Django (ASGI) -> asyncio.create_task() -> Event Loop
OR
Django -> DB Table Queue -> Django Management Command Worker
```

## 2. Why It Exists
Standing up Redis and Celery adds immense operational complexity (2 extra services to monitor, deploy, and scale). For many small-to-medium applications, this is overkill. Django 6.x and the modern Python ecosystem offer lightweight alternatives.

## 3. Internal Working
**Asyncio Background Tasks**: In an ASGI environment, you can attach tasks to the event loop directly. They run concurrently with the request-response cycle.
**Database-backed Queues**: Using libraries like `django-q2` or `django-background-tasks`, tasks are serialized and stored in PostgreSQL. A background process polls the table using `SELECT FOR UPDATE SKIP LOCKED` (Postgres specific) to ensure exactly-once processing without deadlocks.

## 4. Basic Implementation (Asyncio Task)
```python
import asyncio
from django.http import HttpResponse

async def send_email_async(user_id):
    await asyncio.sleep(2) # Simulate I/O
    print(f"Email sent to {user_id}")

async def register_view(request):
    # Fire and forget directly in the ASGI event loop
    asyncio.create_task(send_email_async(request.POST['user_id']))
    return HttpResponse("Registered! Email on the way.")
```

## 5. Production-Ready Implementation (DB Queue)
Using a database-backed queue (e.g., PostgreSQL `SKIP LOCKED` pattern):
```python
# models.py
class TaskQueue(models.Model):
    name = models.CharField(max_length=255)
    payload = models.JSONField()
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

# worker.py (Custom management command)
from django.db import transaction

def process_tasks():
    with transaction.atomic():
        # PostgreSQL specific magic for high-concurrency DB queues
        task = TaskQueue.objects.select_for_update(skip_locked=True)\
                                .filter(status='pending')\
                                .order_by('created_at')\
                                .first()
        if task:
            task.status = 'processing'
            task.save()
            
            # Do work...
            execute_task(task.payload)
            
            task.status = 'completed'
            task.save()
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:** Relying on `asyncio.create_task()` for critical operations (like payments). If the ASGI server restarts or scales down, all in-memory tasks are permanently lost.

## 7. Environment-Specific Behavior
| Tool | Setup Complexity | Durability | Best For |
|------|------------------|------------|----------|
| `asyncio.create_task` | Zero | None | Non-critical logs, metrics |
| DB Queue (Skip Locked) | Low | High | Medium load, critical data |
| Celery + Redis | High | Medium/High | Massive scale, complex routing |

## 8. Local Development Issues
🔴 SYMPTOM: DB Queue worker causes database locks/slowdown.
🔍 CAUSE: Using SQLite in local dev. SQLite does not support `SKIP LOCKED` and only allows one concurrent writer.
🔧 FIX: Use PostgreSQL in local Docker, or run only one worker thread locally.

## 9. Production Issues
🚨 INCIDENT: Database CPU spike to 100%.
- **Investigation:** The custom DB queue worker was polling the `TaskQueue` table every 0.01 seconds in a tight loop.
- **Fix:** Implement exponential backoff in the polling loop (e.g., sleep 1s, then 2s, up to 10s if no tasks are found) or use Postgres `LISTEN/NOTIFY`.

## 10. Failure Simulation
Create 100 tasks in the DB queue. Start 3 worker instances simultaneously. Without `select_for_update(skip_locked=True)`, you will see deadlocks and duplicate processing. With it, tasks are distributed cleanly.

## 11. Decision Matrix
- **Use asyncio tasks:** Analytics pings, pre-warming caches.
- **Use DB Queues (`django-q2`):** Emails, report generation, webhooks (< 50 tasks/second).
- **Use Celery:** Video encoding, massive parallel scraping (> 100 tasks/second).

## 12. Senior-Level Questions
**Q:** How does Postgres `LISTEN/NOTIFY` improve DB queues?
**A:** Instead of polling the DB constantly (SELECT ...), the worker opens a connection and waits passively. When Django inserts a row, it issues a `NOTIFY channel` command. Postgres pushes the event to the worker, reducing DB load to zero when idle.

## 13. Production Checklist
- [ ] Assessed if Celery is truly needed before adoption.
- [ ] Configured `SKIP LOCKED` for DB queues to prevent deadlocks.
- [ ] Handled ASGI worker shutdown gracefully if using memory tasks.
