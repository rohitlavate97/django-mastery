# ASGI Event Loop & Request Multiplexing: A Staff Engineer's Guide [DJANGO 6.1+]

## 1. Mental Model: WSGI vs ASGI Execution

Understanding *why* async Django exists requires visualizing the execution model. 

### WSGI (Synchronous Thread/Process)
```text
Client 1 -> [Thread 1] -> DB Query (3s) [THREAD BLOCKED]
Client 2 -> [Thread 2] -> DB Query (3s) [THREAD BLOCKED]
Client 3 -> [WAITING IN GUNICORN QUEUE] -> (Times out)
```
*In WSGI, if you have 4 Gunicorn worker threads, and 4 users make a slow API call simultaneously, the 5th user gets a 502/Timeout.*

### ASGI (Asynchronous Event Loop)
```text
Client 1 -> [Event Loop] -> Await DB Query (3s) -> (Loop Yields) -> DB Task Suspended
Client 2 -> [Event Loop] -> Await DB Query (3s) -> (Loop Yields) -> DB Task Suspended
Client 3 -> [Event Loop] -> Instant Cache Hit -> Returns Response!
DB 1 Done -> [Event Loop resumes Client 1] -> Returns Response
```
*In ASGI, a single OS thread can handle thousands of concurrent requests by multiplexing I/O.*

---

## 2. Why It Exists (The C10k Problem)

Django added async support (ASGI) incrementally starting in version 3.0, culminating in full async ORM in 4.1+. 
We use ASGI primarily to handle **I/O-bound** concurrency without the memory overhead of spawning thousands of OS threads. Use cases:
- Long-polling APIs
- High-latency third-party API proxies
- WebSockets (via Channels)
- SSE (Server-Sent Events)

---

## 3. Internal Working: Tracing the Event Loop

How does Uvicorn map an HTTP request to an async Django view?

1. **Uvicorn/Daphne** accepts the TCP connection.
2. It parses the HTTP frame and constructs an **ASGI Scope** (a dict representing the request metadata).
3. It calls the ASGI callable application: `application(scope, receive, send)`.
4. **Django's `ASGIHandler`** takes over. It maps the `scope` to a Django `HttpRequest`.
5. Django runs the **Middleware Chain**. If a middleware is sync, Django uses `sync_to_async` to execute it in a threadpool (this is expensive!).
6. Django resolves the URL and executes your `async def` view.
7. The view `await`s a database call. Under the hood, Django's async ORM compiles the query, but sends it to a threadpool adapter (as psycopg2 is sync) or uses the native async driver (like psycopg3 in Django 4.2+).
8. The Event Loop yields, processing other connections.

---

## 4. Basic Implementation vs. Production Implementation

### ❌ The Broken/Basic Way (Ticking Time Bomb)

```python
# views.py
import asyncio
import time
from django.http import JsonResponse

async def bad_async_view(request):
    # 🚨 DANGER 1: Blocking the event loop! 
    # `time.sleep` is synchronous. It will halt the ENTIRE event loop.
    # While this sleeps, NO OTHER USERS CAN BE SERVED BY THIS WORKER.
    time.sleep(5) 
    
    # 🚨 DANGER 2: Calling sync ORM methods in an async view.
    # Django will raise SynchronousOnlyOperation, crashing the view.
    from .models import User
    user_count = User.objects.count()
    
    return JsonResponse({"status": "ok", "users": user_count})
```

### ✅ The Production-Hardened Way

```python
# views.py
import asyncio
import logging
from django.http import JsonResponse
from asgiref.sync import sync_to_async
from .models import User

logger = logging.getLogger(__name__)

async def good_async_view(request):
    try:
        # ✅ PROPER ASYNC SLEEP: Yields control back to the event loop.
        await asyncio.sleep(0.1) 
        
        # ✅ PROPER ASYNC ORM: Using native async ORM methods (Django 4.1+)
        # This uses psycopg3's native async capabilities if configured.
        user_count = await User.objects.acount()
        
        # ✅ CPU-BOUND TASK DELEGATION:
        # What if you have to parse a massive CSV or do crypto hashing?
        # Await it in a threadpool to avoid blocking the event loop.
        heavy_result = await sync_to_async(cpu_heavy_task, thread_sensitive=False)(user_count)
        
        return JsonResponse({"status": "ok", "users": user_count, "calc": heavy_result})
        
    except asyncio.TimeoutError:
        logger.error("Timeout waiting for upstream service")
        return JsonResponse({"error": "Gateway Timeout"}, status=504)
    except Exception as e:
        logger.exception("Unexpected error in async view")
        return JsonResponse({"error": "Internal Server Error"}, status=500)

def cpu_heavy_task(seed):
    """A CPU-bound function that would block the event loop if run directly."""
    import hashlib
    # Takes ~500ms
    return hashlib.sha256(str(seed * 1000000).encode()).hexdigest()
```

---

## 5. Production Incident: Thread Blocking the Event Loop

### 🔴 INCIDENT: Uvicorn Complete Lockup
**Severity:** SEV-1
**Symptoms:** Memory usage was low. CPU usage was 0%. Yet the server stopped responding to all HTTP requests. 
**Investigation:** 
- A flame graph profiling the Uvicorn worker showed it was stuck inside `requests.get()`.
**Root Cause:**
A Junior engineer wrote an `async def` view but used the synchronous `requests` library to fetch data from an external API that went down and hung without a timeout. 
```python
async def proxy_view(request):
    # THIS KILLS THE SERVER
    response = requests.get("http://slow-api.com") 
    return HttpResponse(response.content)
```
Because `requests.get` is a blocking C-level network call, it froze the one and only OS thread running the Uvicorn event loop. All other incoming ASGI connections queued up and timed out.
**🔧 FIX & Prevention:**
We replaced `requests` with `httpx` and enforced timeouts.
```python
import httpx

async def proxy_view(request):
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get("http://slow-api.com")
        return HttpResponse(response.content)
```
**Prevention:** We added a CI linter (`flake8-async`) that forbids `requests` inside any file containing `async def`.

---

## 6. Environment Comparison Matrix

| Environment | Server Runner | Concurrency | DB Driver | Worker Scaling |
| :--- | :--- | :--- | :--- | :--- |
| **Local** | `python manage.py runserver` | Sync threads (fake async) | `psycopg2` | 1 |
| **Local (Uvicorn)** | `uvicorn config.asgi:application`| 1 Event Loop | `psycopg2`/`3` | 1 |
| **Staging/Prod** | `gunicorn -k uvicorn.workers.UvicornWorker` | M Workers x 1 Loop | `psycopg3` (async) | CPU Cores * 2 |

---

## 7. Pytest Test Suite for Async Views

Testing async views requires `pytest-asyncio` and Django's `async_client`.

```python
# test_views.py
import pytest
from django.urls import reverse
from myapp.models import User

# Mark the whole class as async and allow DB access
@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True) 
class TestAsyncViews:
    
    async def test_good_async_view(self, async_client):
        # Arrange
        await User.objects.acreate(username="testuser")
        
        # Act
        url = reverse('good-async-view')
        response = await async_client.get(url)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["users"] == 1
        assert "calc" in data

    async def test_view_timeout_handling(self, async_client, mocker):
        # Simulate an asyncio timeout inside the view
        mocker.patch('asyncio.sleep', side_effect=asyncio.TimeoutError)
        
        response = await async_client.get(reverse('good-async-view'))
        
        assert response.status_code == 504
```

## 8. Checklist: Are you ready for ASGI?
- [ ] Are you using `psycopg3` (or `psycopg` >= 3.1.8) for native async PG?
- [ ] Have you audited all middlewares? (Sync middlewares force Django to context-switch, tanking performance).
- [ ] Have you replaced `requests` with `httpx` or `aiohttp`?
- [ ] Have you wrapped CPU-bound tasks in `sync_to_async`?
