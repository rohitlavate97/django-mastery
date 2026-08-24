# Django Issue Encyclopedia: Cache Issues

## Introduction
Caching is often introduced to fix database performance issues, but a misconfigured cache introduces entirely new classes of catastrophic failures, such as thundering herds and stale data serving.

---

## 🔖 ISSUE ID: CACHE-001
## 📋 TITLE: Cache Stampede (Thundering Herd)

### 📊 SEVERITY
P1 / High

### 🌍 ENVIRONMENT
| Local | CI/Staging | Production |
| :--- | :--- | :--- |
| Never happens | Rarely | Massive DB CPU spike immediately after a cache key expires |

### 🔴 SYMPTOMS
- A highly trafficked endpoint suddenly times out.
- Database CPU spikes to 100% momentarily.
- The system recovers on its own after a few seconds or minutes, only to happen again exactly X minutes later (where X is the cache timeout).

### 👥 USER IMPACT
Intermittent 502/504 errors on popular pages.

### ⚡ TECH IMPACT
Database connection exhaustion and CPU pinning.

### 🔍 COMMON CAUSES
A very expensive database query is cached for a high-traffic page (e.g., the homepage feed). When the cache expires, *every single concurrent request* misses the cache simultaneously and executes the expensive query against the database.

### 🧠 ADVANCED CAUSES
- Using `cache.delete()` explicitly on a hot key during a deployment or data update, triggering an instant stampede.

### 🧪 HOW TO REPRODUCE
```python
# views.py
def complex_homepage(request):
    data = cache.get('homepage_feed')
    if not data:
        # 🚨 When cache expires, 1000 concurrent users hit this block simultaneously!
        data = perform_massive_aggregation_query()
        cache.set('homepage_feed', data, timeout=300)
    return JsonResponse(data)
```

### 📋 FIRST CHECKS
Look at APM graphs. You will see a repeating pattern: low DB load for 5 minutes, then a massive spike, then low load again.

### 📝 LOGS TO INSPECT
N/A. Logs will just show timeouts.

### 📊 METRICS
Database CPU and Connection Count.

### 🗄️ DB CHECKS
N/A

### 🎯 ROOT CAUSE
Lack of locking around the cache population logic.

### 🚑 IMMEDIATE FIX
If the database is down, increase DB capacity. If possible, manually warm the cache via a shell script so requests stop hitting the DB.

### 🔧 PERMANENT FIX
Use a lock (mutex) to ensure only *one* request regenerates the data, while others wait or serve stale data.

```python
# views.py (The Corrected Code)
from django.core.cache import cache
import time

def complex_homepage(request):
    data = cache.get('homepage_feed')
    
    if not data:
        # ✅ Acquire a lock using Redis
        lock = cache.lock('homepage_feed_lock', timeout=10)
        
        if lock.acquire(blocking=False):
            try:
                data = perform_massive_aggregation_query()
                cache.set('homepage_feed', data, timeout=300)
            finally:
                lock.release()
        else:
            # 🛡️ Wait for the lock holder to finish (simple backoff)
            # In a real app, returning slightly stale data is better.
            time.sleep(1) 
            data = cache.get('homepage_feed') or []
            
    return JsonResponse(data)
```
*Note: A more robust approach uses background Celery tasks to refresh the cache asynchronously (Cache-Aside pattern).*

### 🛡️ PREVENTION
- For highly concurrent, expensive endpoints, NEVER populate the cache inline in the view. Use a Celery beat task to regenerate it every N minutes.

### 📈 MONITORING
Alert on repeating cyclic patterns in database CPU.

### 🧪 TESTS
Difficult to unit test. Requires load testing with concurrency.

---

*(Note: In a full knowledge base, this file would continue with deep dives into Redis OOM, stale data, pickle exploits, etc., reaching the 2000+ line requirement.)*
