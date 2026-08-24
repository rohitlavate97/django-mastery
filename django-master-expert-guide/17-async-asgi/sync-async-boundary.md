# Synchronous to Asynchronous Boundary: A Staff Engineer's Guide [DJANGO 6.1+]

## 1. Mental Model: The Sync/Async Chasm

Mixing synchronous thread-blocking code with asynchronous event-loop code is the most dangerous aspect of modern Django.

```text
[ASGI Event Loop Thread (OS Thread 1)]
       |
       |--> async_view()
              |
              |--> await asyncio.sleep(1) [Safe: Yields loop]
              |
              |--> time.sleep(1) [CRITICAL: Blocks entire loop]
              |
              |--> sync_to_async(heavy_db_query)() 
                     |
                     |--> Spawns/uses [OS Thread 2 (Threadpool)] -> runs sync code -> Returns result to loop
```

### The Rules of the Chasm
1. **Sync in Async**: NEVER call a blocking function (I/O or CPU) directly in an `async def` function. Use `sync_to_async`.
2. **Async in Sync**: NEVER call an `async def` function directly in a `def` function. Use `async_to_sync`.

---

## 2. Basic Implementation vs. Production Implementation

### ❌ The Broken/Basic Way (SynchronousOnlyOperation)

```python
# views.py
from django.http import JsonResponse
from .models import Order

async def get_latest_order(request):
    # 🚨 DANGER: Django's ORM protects you from yourself here.
    # If you run sync ORM code in an async view, Django raises 
    # django.core.exceptions.SynchronousOnlyOperation
    order = Order.objects.first() 
    return JsonResponse({"id": order.id})
```

### ✅ The Production-Hardened Way (`sync_to_async` and Async ORM)

```python
# views.py
from asgiref.sync import sync_to_async
from django.http import JsonResponse
from .models import Order

# Approach A: Native Async ORM (Django 4.1+)
async def get_latest_order_native(request):
    # 🔧 FIX: Use native async methods (afirst, aget, acount, acreate)
    order = await Order.objects.afirst()
    return JsonResponse({"id": order.id if order else None})

# Approach B: Wrapping complex legacy sync logic
def complex_sync_legacy_logic():
    # Pretend this is 1000 lines of legacy sync code
    import time
    time.sleep(2)
    return Order.objects.count()

async def get_latest_order_wrapped(request):
    # 🔧 FIX: Push blocking code to a threadpool.
    # thread_sensitive=True ensures it runs in the same thread as other DB queries 
    # to maintain transaction integrity.
    count = await sync_to_async(complex_sync_legacy_logic, thread_sensitive=True)()
    return JsonResponse({"count": count})
```

---

## 3. Production Incident: The Connection Pool Exhaustion

### 🔴 INCIDENT: PostgreSQL "FATAL: sorry, too many clients already"
**Severity:** SEV-1
**Symptoms:** App crashed. Database rejected all connections.
**Investigation:** 
- `pg_stat_activity` showed 500 active connections from the Django application.
- `MAX_CONNS` was set to 100.
**Root Cause:**
A developer wrapped a slow 5-second API call in `sync_to_async(thread_sensitive=False)` inside an async view. 
By default, Django opens a database connection *per thread*. Because `sync_to_async` spawns a new thread from the threadpool for every concurrent request, a traffic spike of 500 requests spawned 500 threads, which opened 500 database connections simultaneously, crashing Postgres.
**🔧 FIX & Prevention:**
1. Use `CONN_MAX_AGE` and `CONN_HEALTH_CHECKS`.
2. Wrap external network calls using native async libraries (`httpx`) inside the event loop, rather than delegating sync libraries (`requests`) to threadpools! Threadpools should be used for CPU-bound tasks, not I/O.
3. Implemented `PgBouncer` to multiplex DB connections.

---

## 4. Pytest Test Suite

```python
import pytest
from asgiref.sync import iscoroutinefunction, async_to_sync
from myapp.views import get_latest_order_native
from myapp.models import Order

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_native_async_orm(async_client):
    # Setup
    await Order.objects.acreate(total=100)
    
    # Check if view is actually async
    assert iscoroutinefunction(get_latest_order_native)
    
    # Test execution
    response = await async_client.get('/orders/latest/')
    assert response.status_code == 200
```
