# Python Concurrency Primitives in Django

## 1. Mental Model
```text
+-------------------------------------------------------------+
|    WSGI / ASGI Gateway (Gunicorn / Uvicorn)                 |
+-------------------------------------------------------------+
|   Processes (Multiprocessing)  --> High Memory, True Paral. |
|       |                                                     |
|       +-- Threads (Threading)  --> Shared Memory, GIL bound |
|               |                                             |
|               +-- AsyncIO (Tasks) --> Cooperative, Single Th|
+-------------------------------------------------------------+
```

## 2. Why It Exists
Django was traditionally synchronous (WSGI), meaning one request = one thread or process. With modern web patterns (WebSockets, slow API integrations), async (ASGI) is essential. However, integrating a sync ORM with an async event loop requires a deep understanding of Python concurrency.

## 3. The GIL (Global Interpreter Lock)
The GIL ensures only one OS thread executes Python bytecode at a time.
- **CPU-bound tasks** in threads are blocked by the GIL.
- **I/O-bound tasks** (like DB queries, HTTP requests) release the GIL.
Because most Django workloads are I/O bound (waiting on Postgres or Redis), multi-threading (Gunicorn gthread workers) is highly effective.

## 4. Multiprocessing & Threading (Gunicorn)
### Prefork Model (Processes)
Gunicorn creates a master process that forks worker processes.
- **Command**: `gunicorn myapp.wsgi -w 4`
- **Isolation**: High. If one worker crashes, others survive.
- **Memory**: High. Each process loads the whole Django app (partially mitigated by Copy-on-Write).

### Threaded Model
- **Command**: `gunicorn myapp.wsgi -w 4 --threads 4`
- **Isolation**: Low. A crash in C-extension kills the process.
- **Memory**: Efficient. Threads share memory.

### Thread Safety in Django
Django's request handling is thread-safe (each thread gets its own request object).
Django's DB connections are thread-local (each thread gets a separate DB connection).
**🔴 Anti-pattern**: Module-level state.
```python
# TICKING TIME BOMB
class PaymentService:
    last_processed_id = None  # Shared across all threads in the process!

    @classmethod
    def process(cls, payment_id):
        cls.last_processed_id = payment_id # Race condition
```

## 5. AsyncIO and Django
Django 3.1+ supports async views. Django 4.1+ supports async ORM.

### Internal Working: `sync_to_async` and `async_to_sync`
Django uses `asgiref.sync.sync_to_async` to run synchronous code (like ORM queries) from an async view. Under the hood, it submits the sync function to a `ThreadPoolExecutor` and yields an async Future, returning the result to the event loop.

```python
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User

# Running sync ORM in async view
async def get_user_count():
    # thread_sensitive=True ensures it runs in the SAME thread context
    # to avoid DB connection pooling issues.
    return await sync_to_async(User.objects.count, thread_sensitive=True)()
```

## 6. Environment-Specific Behavior

| Environment | Default Concurrency | DB Connections | Risk Profile |
|-------------|---------------------|----------------|--------------|
| Local (runserver) | Threaded (WSGI) | 1 per thread | Low |
| Prod (Gunicorn sync) | Processes (Prefork) | 1 per process | Memory heavy |
| Prod (Gunicorn+threads) | Processes * Threads | 1 per thread | DB Conn exhaustion |
| Prod (Uvicorn) | Async Event Loop | Async connection | Threadpool starvation |

## 7. Production Issues
🔴 **INCIDENT**: Postgres connection pool exhaustion.
🔍 **INVESTIGATION**: Gunicorn configured with `-w 8 --threads 10`. Total max connections = 80 per instance. Autoscaling group spun up 10 instances -> 800 DB connections, exceeding Postgres `max_connections` (usually 100).
🔧 **FIX**: Use PgBouncer (transaction pooling) and reduce Gunicorn thread count, or switch to async if heavily IO bound.

## 8. Decision Matrix
- **Heavy CPU task (PDF generation)**: Celery (ProcessPool).
- **Many slow HTTP API calls**: AsyncIO (httpx) + ASGI view.
- **Standard CRUD app**: Gunicorn sync workers with threads.

## 9. Production Checklist
- [ ] No module-level mutable state used for request data.
- [ ] `sync_to_async` explicitly sets `thread_sensitive=True` for DB access.
- [ ] Async views do not call sync blocking functions natively (e.g., `time.sleep`, `requests.get`).
- [ ] Database connection limits account for `Workers * Threads * Instances`.
