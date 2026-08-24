# Concurrency Primitives: Principal/Staff Engineer Deep Dive

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


## 1. Mental Model & Internal Architecture

```text
+-------------------+       +-------------------+       +--------------------+
|                   |       |                   |       |                    |
|  User Request     +------>+  Routing Layer    +------>+ Application Logic  |
|                   |       |                   |       |                    |
+-------------------+       +--------+----------+       +---------+----------+
                                     |                            |
                                     v                            v
                            +--------+----------+       +---------+----------+
                            |                   |       |                    |
                            | Middleware Stack  |       | Core System / ORM  |
                            |                   |       |                    |
                            +-------------------+       +--------------------+
```

### Why It Exists
The Concurrency Primitives exists to solve complex engineering problems in the Django ecosystem. Without it, the application would suffer from tight coupling, lack of scalability, and poor developer ergonomics.

## 2. Django Internal Source Traces

Let's dive into how Concurrency Primitives actually works under the hood in Django 6.1+.

```python
# Django Internal Trace (Conceptual representation)
# Location: django/core/handlers/base.py

class BaseHandler:
    def get_response(self, request):
        # 1. Resolve URL
        resolver_match = self.resolve_request(request)
        
        # 2. Apply Middleware
        response = self._middleware_chain(request)
        
        # 3. Execute View
        if response is None:
            response = resolver_match.func(request, *resolver_match.args, **resolver_match.kwargs)
            
        return response
```
*Notice how the execution flows from the base handler through the middleware chain down to the view layer.*

## 3. Basic vs Production-Ready Implementation

### Naive Implementation (Anti-Pattern)
```python
# TICKING TIME BOMB: Do not use in production
def basic_approach(request):
    data = do_something_expensive()
    return HttpResponse(data)
```

### Production-Hardened Implementation
```python
import logging
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger(__name__)

def production_ready_approach(request):
    try:
        # 1. Check Cache
        cache_key = f"data_{request.user.id}"
        data = cache.get(cache_key)
        
        if not data:
            # 2. Perform Operation with Timeout
            data = do_something_expensive(timeout=2.0)
            cache.set(cache_key, data, timeout=300)
            
        return JsonResponse({"status": "success", "data": data})
        
    except Exception as e:
        logger.error(f"Failed to process request: {str(e)}", exc_info=True)
        return JsonResponse({"status": "error", "message": "Internal Server Error"}, status=500)
```

## 4. Environment-Specific Behavior Matrix

| Environment | Configuration | Behavior | Common Issue |
|-------------|---------------|----------|--------------|
| **Local** | `DEBUG=True` | Synchronous, verbose logging | Masking N+1 queries |
| **Docker** | `DEBUG=False` | Containerized, isolated | Volume mounting latency |
| **CI/CD** | `DEBUG=False` | Mocked external services | Flaky tests on timing |
| **Staging** | `DEBUG=False` | Replica DB, high cache TTL | Cache invalidation bugs |
| **Prod (100k RPS)**| `DEBUG=False` | Read replicas, load balanced | Connection pool exhaustion|

## 5. 3:00 AM Production Incident: Concurrency Primitives Failure

🔴 **SYMPTOM**: At 3:15 AM on Black Friday, p99 latency spiked to 15s. HTTP 502 Bad Gateway errors spiked to 4%.

🔍 **CAUSE**: Connection pool exhaustion due to a slow query locking the main thread.

**Timeline:**
- 03:00 AM: Traffic increased by 400%
- 03:10 AM: Database CPU hit 95%
- 03:15 AM: Gunicorn workers starved, queuing requests

🔧 **DEBUG & FIX**:
```bash
# Debugging commands used
$ tail -f /var/log/nginx/error.log
$ htop
$ psql -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"
```

**Permanent Fix**:
Implemented pgbouncer for connection pooling and added a 2-second statement timeout to PostgreSQL.

## 6. Pytest Verification & Edge Cases

```python
import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_concurrency_primitives_edge_case(client, mocker):
    # Arrange
    mocker.patch('my_app.services.expensive_call', side_effect=TimeoutError)
    
    # Act
    response = client.get(reverse('my_endpoint'))
    
    # Assert
    assert response.status_code == 500
    assert "error" in response.json()
```

## 7. Decision Matrix & Checklist

**When to use:**
- ✅ High throughput read-heavy workloads
- ❌ Write-heavy transactional systems

**Production Checklist:**
- [ ] Added Datadog APM tracing
- [ ] Configured PagerDuty alerts for >5% error rate
- [ ] Reviewed query plans with `EXPLAIN ANALYZE`
- [ ] Load tested with `locust` up to 10k concurrent users

---
*Enhanced for Principal/Staff Engineer Depth (Django 6.1+, Python 3.12+, PostgreSQL 16+)*
