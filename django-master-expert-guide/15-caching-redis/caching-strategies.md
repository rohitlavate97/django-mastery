# Caching Strategies in Django

## 1. Mental Model
```text
[Cache-Aside]
App -> Asks Cache -> Miss -> Asks DB -> Updates Cache -> Returns Data

[Read-Through]
App -> Asks Cache Provider -> (Cache automatically queries DB if miss) -> Returns Data

[Write-Through]
App -> Writes to Cache Provider -> (Cache syncs to DB) -> Returns Success

[Write-Behind / Write-Back]
App -> Writes to Cache -> Returns Success -> (Cache asynchronously writes to DB later)
```

## 2. Why It Exists
Caching isn't a one-size-fits-all solution. Depending on whether your application is read-heavy (e.g., a news site) or write-heavy (e.g., IoT data ingestion), you need different strategies to optimize performance and prevent bottlenecks.

## 3. Internal Working
Django primarily uses **Cache-Aside** (lazy loading). The application code is explicitly responsible for checking the cache, querying the database on a miss, and populating the cache.

## 4. Basic Implementation
**Cache-Aside Pattern in Django:**

```python
from django.core.cache import cache
from .models import Article

def get_popular_articles():
    # 1. Ask Cache
    articles = cache.get('popular_articles')
    
    if not articles:
        # 2. Miss -> Ask DB
        articles = list(Article.objects.filter(views__gt=1000))
        # 3. Update Cache
        cache.set('popular_articles', articles, timeout=3600)
        
    # 4. Return Data
    return articles
```
*Note: Django provides a shortcut for this called `cache.get_or_set()`.*

## 5. Production-Ready Implementation
**Stale-While-Revalidate Pattern** (A mitigation for Cache Stampedes):
Instead of making users wait for the DB query when the cache expires, serve slightly stale data while regenerating the cache in the background (using Celery).

```python
from django.core.cache import cache
from .tasks import regenerate_popular_articles

def get_popular_articles():
    # Store a tuple: (data, generation_timestamp)
    cached_data = cache.get('popular_articles')
    
    if cached_data:
        data, timestamp = cached_data
        # If data is older than 50 minutes (but TTL is 60), trigger background refresh
        if (timezone.now().timestamp() - timestamp) > 3000:
            regenerate_popular_articles.delay() # Celery task
        return data
        
    # Hard miss (cache completely empty)
    data = fetch_from_db()
    cache.set('popular_articles', (data, timezone.now().timestamp()), timeout=3600)
    return data
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:**
```python
# Write-Through attempted poorly
def update_user_score(user_id, score):
    cache.set(f"user_score_{user_id}", score)
    User.objects.filter(id=user_id).update(score=score)
```
*Why it's bad:* If the DB update fails, your cache now has invalid data (a dirty read). Always update the DB *first*, or use `transaction.on_commit` to update the cache only after a successful DB write.

## 7. Environment-Specific Behavior
| Strategy | Implementation in Django | Best For |
|----------|--------------------------|----------|
| Cache-Aside | Native (`cache.get_or_set`) | 90% of general web read workloads |
| Read-Through | Requires custom backend/middleware | Abstraction layers |
| Write-Behind | Redis + Celery | High-volume writes (analytics, likes) |

## 8. Local Development Issues
🔴 SYMPTOM: You implemented Write-Behind caching, but data never saves locally.
🔍 CAUSE: Your local environment is using `DummyCache` or Celery is configured to run eagerly (`task_always_eager=True`), causing unexpected synchronous execution that hides race conditions.
🔧 FIX: Use a local Redis instance and run a real Celery worker when testing Write-Behind patterns.

## 9. Production Issues
🔴 INCIDENT: Out of Memory (OOM) on Database
- **Severity:** HIGH
- **Investigation:** A Write-Behind pattern for "Video Views" was dumping millions of updates to the DB during peak hours.
- **Root Cause:** The background task was processing individual writes instead of batching them.
- **Fix:** Changed the Write-Behind task to pull keys from Redis, aggregate them, and perform a single `bulk_update()` every 5 minutes.

## 10. Failure Simulation
Implement a standard Cache-Aside pattern. Then, manually clear your Redis cache (`FLUSHALL`). Observe the spike in DB queries. This demonstrates the "cold start" problem inherent to Cache-Aside.

## 11. Decision Matrix
| Strategy | Pros | Cons |
|----------|------|------|
| Cache-Aside | Simple, resilient to cache failure | Cold start latency |
| Stale-While-Revalidate | Zero latency on expiration | Complexity, requires background workers |
| Write-Behind | Insulates DB from write spikes | High risk of data loss if cache dies before DB sync |

## 12. Senior-Level Questions
**Q: How do you implement a Write-Behind cache for a "Like" button in Django?**
A: When a user clicks "Like", increment a Redis counter (`INCR post:123:likes`). Do *not* touch the DB. Run a Celery beat task every 5 minutes that reads all `post:*:likes` keys, writes them to the DB using `Post.objects.bulk_update()`, and then deletes the Redis keys.

## 13. Production Checklist
- [ ] Read-heavy endpoints utilize Cache-Aside.
- [ ] Highly concurrent endpoints utilize Stale-While-Revalidate.
- [ ] Cache updates are deferred until `transaction.on_commit()`.
