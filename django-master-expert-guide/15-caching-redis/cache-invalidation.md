# Cache Invalidation Strategies

## 1. Mental Model
```text
[DB Update] ----> (Invalidation Trigger)
                         |
                         v
                  [Delete Key / Increment Version]
                         |
                         v
[Next Request] -> Cache Miss -> [Recompute] -> [Store New Value]
```

## 2. Why It Exists
"There are only two hard things in Computer Science: cache invalidation and naming things." 
Stale cache data leads to inconsistent user experiences (e.g., a user updates their profile, but the old name is still displayed). Invalidation ensures the cache remains synchronized with the source of truth (the database).

## 3. Internal Working
Invalidation typically works in one of two ways:
1. **Explicit Deletion:** Deleting the cache key (`cache.delete(key)`).
2. **Key Versioning:** Changing the key name or version parameter so subsequent requests look for a new key, letting the old one expire naturally via TTL.

## 4. Basic Implementation
Using Django Signals to delete a cache key when a model is updated.

```python
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import UserProfile

@receiver(post_save, sender=UserProfile)
@receiver(post_delete, sender=UserProfile)
def invalidate_user_profile_cache(sender, instance, **kwargs):
    cache_key = f"user_profile_{instance.user_id}"
    cache.delete(cache_key)
```

## 5. Production-Ready Implementation
Key versioning is often safer than deletion in high-concurrency environments to avoid race conditions.

```python
from django.core.cache import cache

def get_profile_version_key(user_id):
    return f"profile_version_{user_id}"

def get_user_profile_cache(user_id):
    # Fetch the current version, default to 1
    version = cache.get(get_profile_version_key(user_id), 1)
    
    cache_key = f"user_profile_{user_id}"
    
    # Use Django's built-in versioning
    profile_data = cache.get(cache_key, version=version)
    
    if profile_data is None:
        profile_data = fetch_profile_from_db(user_id)
        cache.set(cache_key, profile_data, timeout=3600, version=version)
        
    return profile_data

# Invalidation is just bumping the version
def invalidate_profile(user_id):
    version_key = get_profile_version_key(user_id)
    try:
        cache.incr(version_key)
    except ValueError:
        # If the key doesn't exist, start at 2
        cache.set(version_key, 2)
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:**
```python
# Relying purely on signals for complex invalidation
@receiver(post_save, sender=Post)
def clear_homepage_cache(sender, instance, **kwargs):
    cache.delete("homepage_feed")
```
*Why it's bad:* In a bulk update (`Post.objects.update(...)`), signals are NOT triggered. The cache will remain stale. Signals are also synchronous; deleting cache during a transaction can cause race conditions if the transaction rolls back.

## 7. Environment-Specific Behavior
| Strategy | Local | Production |
|----------|-------|------------|
| Signal Deletion | Fine | Prone to race conditions during DB transactions |
| Key Versioning | Unnecessary | Highly recommended for distributed setups |

## 8. Local Development Issues
🔴 SYMPTOM: Updated data isn't showing up on the frontend.
🔍 CAUSE: Cache invalidation logic missed a specific update path (e.g., a background Celery task updated the DB without triggering invalidation).
🔧 FIX: Centralize update logic (e.g., Services layer) and ensure cache invalidation happens there, rather than relying exclusively on model signals.

## 9. Production Issues
🔴 INCIDENT: Race Condition during Transaction
- **Severity:** MEDIUM
- **Investigation:** Cache was sometimes showing stale data immediately after a save.
- **Root Cause:** A signal deleted the cache key, another request immediately reconstructed the cache using *stale* DB data because the original transaction hadn't committed yet.
- **Fix:** Use `transaction.on_commit()` to defer cache deletion until the database changes are visible to all connections.

```python
from django.db import transaction

@receiver(post_save, sender=UserProfile)
def invalidate_safely(sender, instance, **kwargs):
    transaction.on_commit(lambda: cache.delete(f"profile_{instance.id}"))
```

## 10. Failure Simulation
Update a model using `.update()` instead of `.save()`. Observe that signals don't fire and the cache isn't invalidated. This proves the limitation of signal-based invalidation.

## 11. Decision Matrix
| Invalidation | Pros | Cons |
|--------------|------|------|
| TTL (Time-to-live) | Zero logic required | Data is stale until TTL expires |
| Signal Deletion | Easy to implement | Misses bulk operations, race conditions |
| Versioning | Prevents race conditions, atomic | Requires tracking version state |

## 12. Senior-Level Questions
**Q: How do you invalidate cache for a list view (e.g., `/posts/`) when a single item is updated?**
A: This is complex. Options: 
1. Key versioning on the list based on the latest updated timestamp of the collection.
2. Store individual items in cache and assemble the list view dynamically.
3. Overwrite the specific item in the cached list (Write-through), though this is complex with pagination.

## 13. Production Checklist
- [ ] All cache invalidation within transactions uses `transaction.on_commit()`.
- [ ] Bulk operations (`update()`, `bulk_create()`) have manual cache invalidation steps.
- [ ] Cache keys use a consistent naming convention to avoid collisions.
