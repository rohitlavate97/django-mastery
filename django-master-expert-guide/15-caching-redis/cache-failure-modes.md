# Cache Failure Modes

## 1. Mental Model
```text
[Healthy State]
Traffic -> Cache -> (Miss) -> DB (Small Load)

[Failure Mode: Thundering Herd / Stampede]
Traffic -> Cache Expires! -> 1000 Requests -> DB (CRASH!)

[Failure Mode: Penetration]
Traffic (Malicious) -> Requests Key 'XYZ' -> Cache Miss -> DB Miss -> (Repeats forever)

[Failure Mode: Avalanche]
Traffic -> Redis Server Dies -> All Cache Fails -> DB takes 100% Load (CRASH!)
```

## 2. Why It Exists
Distributed systems fail. If your application's survival depends on the cache being up 100% of the time, your architecture is fragile. Understanding failure modes allows you to build resilient systems that degrade gracefully rather than crashing completely.

## 3. Internal Working
- **Stampede:** Occurs when a highly popular key expires, and thousands of concurrent requests all hit the DB simultaneously to regenerate it.
- **Penetration:** Occurs when attackers request data that doesn't exist. Since it doesn't exist, it's never cached, forcing a DB query on every request.
- **Avalanche:** Occurs when many keys expire at the exact same time, or the cache server reboots.

## 4. Basic Implementation (Mitigating Penetration)
To prevent cache penetration, you must cache the *absence* of data.

```python
from django.core.cache import cache
from .models import Product

def get_product(product_id):
    cache_key = f"prod_{product_id}"
    product = cache.get(cache_key)
    
    if product is None:
        try:
            product = Product.objects.get(id=product_id)
            cache.set(cache_key, product, timeout=3600)
        except Product.DoesNotExist:
            # Cache the fact that it DOES NOT EXIST to prevent future DB hits
            cache.set(cache_key, "NOT_FOUND", timeout=300) # Shorter TTL for negative cache
            return None
            
    if product == "NOT_FOUND":
        return None
        
    return product
```

## 5. Production-Ready Implementation (Mitigating Stampede)
Use a distributed lock (Mutex) so only the *first* request queries the DB, while others wait.

```python
from django.core.cache import cache
from django.core.cache.backends.base import DEFAULT_TIMEOUT
import time

def get_heavy_report():
    data = cache.get('heavy_report')
    if data:
        return data

    # Attempt to acquire a lock
    lock_id = "lock_heavy_report"
    acquired = cache.add(lock_id, "true", timeout=10) # 10s lock timeout
    
    if acquired:
        try:
            # We are the first! Generate the report.
            data = generate_heavy_report()
            cache.set('heavy_report', data, timeout=3600)
            return data
        finally:
            cache.delete(lock_id)
    else:
        # We are the herd. Wait and retry.
        time.sleep(0.5)
        return cache.get('heavy_report') # Hopefully populated by the lock owner
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:**
```python
# Caching a large QuerySet directly
def get_all_users():
    return cache.get_or_set('all_users', User.objects.all(), timeout=86400)
```
*Why it's bad:* Caching an unevaluated QuerySet actually caches the *SQL query*, not the data. Furthermore, if you force evaluation (e.g., `list(User.objects.all())`), you pull massive amounts of data into memory, potentially causing OOM on Redis or the Django worker.

## 7. Environment-Specific Behavior
| Failure Mode | Local | Production |
|--------------|-------|------------|
| Stampede     | Impossible to trigger | Frequent during traffic spikes |
| Avalanche    | N/A | Happens during scheduled Redis maintenance |

## 8. Local Development Issues
🔴 SYMPTOM: You implemented a lock, but it randomly deadlocks locally.
🔍 CAUSE: Your code throws an exception inside the lock, bypassing the `cache.delete(lock_id)` cleanup.
🔧 FIX: Always use `try/finally` blocks when implementing locks manually, or use a context manager provided by libraries like `python-redis-lock`.

## 9. Production Issues
🔴 INCIDENT: Cache Avalanche brought down production.
- **Severity:** CRITICAL
- **Investigation:** At midnight, the DB CPU spiked to 100% and connections maxed out.
- **Root Cause:** A nightly cron job was clearing the entire cache (`cache.clear()`). All subsequent requests experienced a cache miss, shifting 100% of the load to the database instantly.
- **Fix:** Removed global cache clearing. Implemented rolling TTLs (adding random jitter to cache timeouts so they don't all expire exactly at midnight).

```python
import random
# Add 0 to 5 minutes of jitter to the 1-hour timeout
timeout = 3600 + random.randint(0, 300) 
cache.set(key, value, timeout)
```

## 10. Failure Simulation
Use a load testing tool like `locust` or `wrk` to send 500 requests per second to a single cached endpoint. Then, manually delete the cache key. Observe the DB load spike. Implement a mutex lock and repeat the test; observe the DB load remain stable at 1 query.

## 11. Decision Matrix
| Failure Mode | Best Mitigation | Complexity |
|--------------|-----------------|------------|
| Stampede | Stale-While-Revalidate | High |
| Penetration | Negative Caching | Low |
| Avalanche | TTL Jitter | Low |
| Redis Outage | Fallback to DB (Graceful Degradation) | Medium |

## 12. Senior-Level Questions
**Q: What happens to Django if the Redis server goes offline completely?**
A: By default, `django-redis` will raise a `ConnectionError` and crash the request (500 error). To fix this, set `"IGNORE_EXCEPTIONS": True` in your `CACHES` configuration. This tells Django to log the error, treat the cache operation as a miss, and fallback to the database.

## 13. Production Checklist
- [ ] Missing DB records are cached (Negative Caching).
- [ ] Cache timeouts include random jitter to prevent avalanches.
- [ ] Highly concurrent expensive queries use Mutex locks.
- [ ] `IGNORE_EXCEPTIONS = True` is configured to prevent Redis outages from crashing Django.
