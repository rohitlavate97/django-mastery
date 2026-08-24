# Redis Caching Deep Dive: A Staff Engineer's Guide [DJANGO 6.1+]

## 1. Mental Model: Redis Topologies & Data Flows

Using Redis as a cache isn't just about key-value lookups. It's about memory architecture, eviction policies, and cluster topologies.

### Standalone vs Cluster Topology
```text
[Standalone - Local/Dev]            [Cluster / Sentinel - Production]

   +---------------+                  +---------------+   +---------------+
   |               |                  | Redis Master  |-->| Redis Replica |
   |  Redis Node   |                  | (Writes/Reads)|   | (Failover)    |
   | (Single Core) |                  +---------------+   +---------------+
   |               |                         |
   +---------------+                         v (Sharding via Hash Slots)
                                      +---------------+   
                                      | Redis Master 2|   
                                      | (Writes/Reads)|   
                                      +---------------+   
```

### The Cache Stampede Problem (Thundering Herd)
```text
State: Key 'popular_article' expires at 12:00:00.
Time 12:00:01: 500 concurrent users request the article.
Flow:
1. All 500 users check cache -> MISS.
2. All 500 users hit the DB simultaneously.
3. DB CPU hits 100%, crashes.
```
*We will solve this below using Mutex Locking.*

---

## 2. Why It Exists (I/O Bound Architecture)

A PostgreSQL query might take 15ms. A Redis lookup takes 0.5ms. When handling 10,000 requests per second, that 14.5ms delta is the difference between surviving a traffic spike and total downtime. Redis stores data entirely in RAM, bypassing disk I/O entirely.

---

## 3. Internal Working: Tracing `cache.get()`

When you call `cache.get('my_key')` using `django-redis`:
1. **Django Core**: `django.core.cache` proxies the call to the configured backend.
2. **django-redis**: The `RedisCache` class converts the string key to a bytes representation, optionally prepending a prefix (e.g., `CACHE_KEY_PREFIX`).
3. **Serialization**: It checks if it needs to deserialize the data (Pickle is default, JSON is safer).
4. **Network I/O**: `redis-py` acquires a connection from the Threaded Connection Pool.
5. It executes the `GET` command over the TCP socket.
6. **Deserialization**: Upon return, it unpickles the byte stream into a Python object.

---

## 4. Basic Implementation vs. Production Implementation

### ❌ The Broken/Basic Way (Ticking Time Bomb)

```python
# views.py
from django.core.cache import cache
from .models import HeavyReport

def get_report(request):
    # 🚨 DANGER 1: No handling of Cache Stampede
    # 🚨 DANGER 2: Pickle injection vulnerability (if Redis is compromised)
    report_data = cache.get('monthly_report')
    
    if not report_data:
        # If this takes 5 seconds, and 100 users hit this simultaneously,
        # you execute 100 heavy queries.
        report = HeavyReport.objects.generate_complex_stats()
        cache.set('monthly_report', report, timeout=3600)
        report_data = report
        
    return JsonResponse(report_data)
```

### ✅ The Production-Hardened Way (Mutex Locking)

```python
# views.py
import time
from django.core.cache import cache
from django_redis import get_redis_connection
from .models import HeavyReport

def get_report(request):
    cache_key = 'monthly_report'
    report_data = cache.get(cache_key)
    
    if report_data is not None:
        return JsonResponse(report_data)

    # 🔧 FIX: Mutex Lock to prevent Cache Stampede
    lock_key = f"{cache_key}_lock"
    # Acquire a lock that expires in 10s to prevent deadlocks if process crashes
    lock_acquired = cache.add(lock_key, "locked", timeout=10) 
    
    if lock_acquired:
        try:
            # We got the lock! We are the chosen thread to do the heavy work.
            report = HeavyReport.objects.generate_complex_stats()
            # 🔧 FIX: Add jitter to expiration to prevent simultaneous mass-expiry
            jitter = 3600 + random.randint(-60, 60)
            cache.set(cache_key, report, timeout=jitter)
            return JsonResponse(report)
        finally:
            # Always release the lock
            cache.delete(lock_key)
    else:
        # We didn't get the lock. Someone else is calculating it.
        # Wait a bit and try pulling from cache again.
        time.sleep(0.5)
        report_data = cache.get(cache_key)
        if report_data:
            return JsonResponse(report_data)
        # Fallback if calculation is taking too long
        return JsonResponse({"error": "Report generating..."}, status=202)
```

```python
# settings.py Configuration
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            # 🔧 FIX: Use JSON instead of Pickle for security
            "SERIALIZER": "django_redis.serializers.json.JSONSerializer",
            # 🔧 FIX: Connection pooling
            "CONNECTION_POOL_KWARGS": {"max_connections": 100},
            # 🔧 FIX: Socket timeouts prevent hung Django threads
            "SOCKET_CONNECT_TIMEOUT": 2, 
            "SOCKET_TIMEOUT": 2,
        }
    }
}
```

---

## 5. Production Incident: The Cache Avalanche

### 🔴 INCIDENT: Total Database Collapse at Midnight
**Severity:** SEV-1
**Symptoms:** At exactly 00:00:00 UTC, the PostgreSQL database CPU hit 100% and crashed.
**Investigation:** 
- Log analysis showed a massive spike in SELECT queries across 50 different tables exactly at midnight.
- All these queries were related to daily aggregated views.
**Root Cause:**
A cron job ran at midnight that cleared the *entire* cache `cache.clear()`. Because *every single cached item* expired at the exact same millisecond, the next thousands of incoming HTTP requests all resulted in Cache Misses, flooding the database simultaneously.
**🔧 FIX & Prevention:**
1. **Never use `cache.clear()` in production.**
2. **Versioned Caching / Key Invalidation:** Instead of clearing, update the key version.
3. **Cache Jitter:** When setting timeouts, always add random jitter so keys expire gradually over a window, not instantaneously.

---

## 6. Environment Comparison Matrix

| Environment | Django Cache Backend | Redis Eviction Policy | Memory |
| :--- | :--- | :--- | :--- |
| **Local** | `LocMemCache` (or Docker Redis) | `noeviction` | 256MB |
| **CI/Pytest** | `LocMemCache` | N/A | N/A |
| **Staging** | `RedisCache` (Standalone) | `allkeys-lru` | 1GB |
| **Production** | AWS ElastiCache / Redis Cluster | `volatile-lru` | 16GB+ |

---

## 7. Pytest Test Suite for Caching Logic

```python
# test_caching.py
import pytest
from unittest.mock import patch
from django.core.cache import cache
from django.urls import reverse

@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield

@pytest.mark.django_db
class TestReportCaching:
    
    @patch('myapp.models.HeavyReport.generate_complex_stats')
    def test_cache_hit_prevents_db_query(self, mock_generate, client):
        # Arrange: mock the DB calculation
        mock_generate.return_value = {"data": "stats"}
        
        # Act 1: First call (Cache Miss)
        client.get(reverse('get_report'))
        assert mock_generate.call_count == 1
        
        # Act 2: Second call (Cache Hit)
        client.get(reverse('get_report'))
        
        # Assert: Function was NOT called a second time
        assert mock_generate.call_count == 1
        
    @patch('myapp.views.cache.add')
    def test_cache_stampede_mutex_waits(self, mock_cache_add, client):
        # Simulate that another thread already has the lock
        mock_cache_add.return_value = False
        
        # Call the view. It should sleep and return 202 or fetch the eventual cache.
        response = client.get(reverse('get_report'))
        assert response.status_code == 202
```
