# Advanced Django Cache Invalidation: A Staff Engineer's Guide [DJANGO 6.1+]

## 1. Mental Model: Cache Invalidation Topology

Phil Karlton famously said, "There are only two hard things in Computer Science: cache invalidation and naming things." 

```text
+---------------+       [Write/Update]        +------------------+
|               | --------------------------> |                  |
| Django Client |                             | PostgreSQL (DB)  |
|               | <---- [Cache Miss/Read] --- |                  |
+---------------+                             +------------------+
      |      ^
      |      |
 [Set/Delete]| [Cache Hit]
      v      |
+------------------+
| Redis Cache      |
| (Key-Value)      |
+------------------+
```

### The Three Invalidation Strategies
1. **Time-To-Live (TTL)**: Passive invalidation. (Weakest)
2. **Event-Driven Invalidation**: Deleting keys via Django signals or ORM overrides. (Standard)
3. **Key Versioning (Cache Tagging)**: Incrementing a version number attached to a resource. (Enterprise)

---

## 2. Why It Exists (The Stale Data Problem)

If an admin updates a Product's price from $10 to $20, but the cache TTL is 24 hours, users will continue checking out with the $10 price. You must evict or update the cached data exactly when the source of truth (the database) mutates.

---

## 3. Basic Implementation vs. Production Implementation

### ❌ The Broken/Basic Way (Ticking Time Bomb)

```python
# models.py
from django.db import models
from django.core.cache import cache

class Product(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)

# views.py
def product_detail(request, product_id):
    # 🚨 DANGER: Cache is set for 1 hour. If price changes, it's stale.
    data = cache.get(f'product_{product_id}')
    if not data:
        data = Product.objects.get(id=product_id)
        cache.set(f'product_{product_id}', data, 3600)
    return JsonResponse({'price': data.price})
```

### ✅ The Production-Hardened Way (Event-Driven & Versioning)

```python
# models.py
from django.db import models
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

class Product(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    @property
    def cache_key(self):
        return f"product_{self.id}"
        
    @property
    def version_key(self):
        return f"product_version_{self.id}"

# 🔧 FIX: Signal-based Cache Invalidation
@receiver([post_save, post_delete], sender=Product)
def invalidate_product_cache(sender, instance, **kwargs):
    # Option A: Delete the key (Simple)
    cache.delete(instance.cache_key)
    
    # Option B: Key Versioning (Advanced)
    # Increment the version. Next read will use the new version, 
    # old version naturally expires via Redis LRU.
    try:
        cache.incr(instance.version_key)
    except ValueError:
        cache.set(instance.version_key, 1, timeout=None)

# views.py
def product_detail(request, product_id):
    version_key = f"product_version_{product_id}"
    version = cache.get(version_key, 1)
    
    cache_key = f"product_{product_id}_v{version}"
    
    data = cache.get(cache_key)
    if not data:
        data = Product.objects.get(id=product_id)
        # Store with the specific version
        cache.set(cache_key, data, 3600)
        
    return JsonResponse({'price': data.price})
```

---

## 4. Production Incident: The Signal Blackhole

### 🔴 INCIDENT: Bulk Update Ignored Cache Invalidation
**Severity:** SEV-2
**Symptoms:** After running a script to apply a 10% discount to all products, the website continued showing old prices.
**Investigation:** 
- `cache.get()` was returning stale data.
- The invalidation signals (`post_save`) did not fire.
**Root Cause:**
A developer ran `Product.objects.update(price=F('price') * 0.9)` in a celery task. Django's `.update()` acts directly on the SQL level and **bypasses all Django signals**. The `post_save` signal was never triggered.
**🔧 FIX & Prevention:**
Overrode the custom queryset/manager to clear caches, or explicitly cleared them in the task.
```python
# tasks.py
def apply_discount():
    # .update() bypasses signals!
    Product.objects.update(price=F('price') * 0.9)
    
    # 🔧 FIX: Must manually invalidate or use a bulk invalidation strategy
    cache.delete_pattern("product_*") # If using Redis natively
```

---

## 5. Pytest Test Suite

```python
import pytest
from django.core.cache import cache
from myapp.models import Product

@pytest.mark.django_db
class TestCacheInvalidation:
    
    def test_product_save_invalidates_cache(self):
        # Arrange
        product = Product.objects.create(name="Laptop", price=1000)
        cache.set(product.cache_key, "stale_data")
        
        # Act
        product.price = 900
        product.save() # Triggers post_save
        
        # Assert
        assert cache.get(product.cache_key) is None
```
