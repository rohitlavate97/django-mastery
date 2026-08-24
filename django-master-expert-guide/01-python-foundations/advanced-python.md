# Advanced Python: Principal/Staff Engineer Deep Dive

# Advanced Python Concepts for Django Mastery

## 1. Mental Model
```text
+-------------------------------------------------------+
|  DJANGO FRAMEWORK (High-Level Abstractions)           |
|  Views | Models | ORM | Middleware | Forms          |
+-------------------------------------------------------+
|                 BRIDGE (Python Magic)                 |
|  Decorators | Metaclasses | Descriptors | Context Mgrs|
+-------------------------------------------------------+
|  PYTHON RUNTIME (Low-Level Execution)                 |
|  Objects | Classes | Types | Functions | Generics     |
+-------------------------------------------------------+
```

## 2. Why It Exists
Django provides an elegant API, but under the hood, it heavily relies on Python's most advanced dynamic features. You cannot master Django without mastering how Python constructs classes dynamically (metaclasses), handles attribute access (descriptors), manages execution flow (decorators and context managers), and handles types. 

## 3. Decorators
### Mental Model
A decorator is a callable that takes another callable and extends its behavior without modifying it.
Django uses decorators extensively: `@login_required`, `@transaction.atomic`, `@api_view`.

### Internal Working: Django's `@login_required`
Django's `login_required` uses `user_passes_test` which internally uses `functools.wraps`.
```python
# Django Internal trace (django.contrib.auth.decorators)
def user_passes_test(test_func, login_url=None, redirect_field_name=REDIRECT_FIELD_NAME):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if test_func(request.user):
                return view_func(request, *args, **kwargs)
            # ... redirect logic ...
        return _wrapped_view
    return decorator
```

### Basic vs Production Implementation
**🔴 Anti-Pattern (Ticking Time Bomb)**: Forgetting `@functools.wraps`
```python
def my_decorator(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper
```
*Symptom*: Django routing might fail, OpenAPI docs will show `wrapper` instead of the view name.

**✅ Production-Ready Implementation**:
```python
import functools
import logging

logger = logging.getLogger(__name__)

def require_company_active(func):
    """Ensures the user's company is active before allowing access."""
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            logger.warning("Unauthenticated access attempt to %s", func.__name__)
            return HttpResponseForbidden("Not authenticated")
        
        if not request.user.company.is_active:
            logger.warning("Inactive company access attempt by %s", request.user.id)
            return HttpResponseForbidden("Company is inactive")
            
        return func(request, *args, **kwargs)
    return wrapper
```

## 4. Descriptors (The Magic Behind Django Models)
### Mental Model
Descriptors are classes that implement `__get__`, `__set__`, or `__delete__`. When you access a class attribute, Python checks if it's a descriptor. If yes, it calls the descriptor's methods instead of regular dictionary lookup.

### Internal Working: Django Fields
Django models use the descriptor protocol heavily. When you define `name = models.CharField()`, the `CharField` contributes a descriptor to the model class.
```python
# Django internal concept
class ForwardManyToOneDescriptor:
    def __get__(self, instance, cls=None):
        if instance is None:
            return self
        # Fetch from DB or cache...
```

### Production Issue 
🔴 **SYMPTOM**: High memory usage and N+1 queries appearing from nowhere on model property access.
🔍 **CAUSE**: Using a property that does database lookups implicitly within loops, without `select_related`.
🔧 **FIX**: Use `cached_property` or explicit querysets.

## 5. Metaclasses (Django's ModelBase)
### Mental Model
If objects are instances of classes, classes are instances of metaclasses. The default metaclass is `type`.
```text
Instance ---> Class ---> Metaclass (type)
my_user  ---> User  ---> ModelBase ---> type
```

### Internal Working: `ModelBase`
When Django parses a model class, `ModelBase.__new__` intercepts the creation, collects all Field instances, sets up the `_meta` API (Options class), and wires up signals.

## 6. Context Managers
### Basic vs Production
Django uses them for DB transactions (`transaction.atomic`).

**✅ Production Implementation**:
```python
from contextlib import contextmanager
import time
import logging

logger = logging.getLogger(__name__)

@contextmanager
def query_timer(name):
    """Context manager to profile specific blocks of query execution."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        logger.info(f"Block '{name}' took {duration:.4f}s")
        if duration > 1.0:
            logger.warning(f"SLOW EXECUTION in '{name}': {duration:.4f}s")

# Usage:
# with query_timer("complex_aggregation"):
#     report = Report.objects.aggregate(...)
```

## 7. Generators and Iterators
QuerySets are lazy and iterable. They use generators internally to yield chunks of results using `iterator(chunk_size=2000)`.

## 8. Magic Methods
- `__str__`: Used by Django Admin for object representation.
- `__bool__`: `bool(QuerySet)` triggers a database query unless you use `QuerySet.exists()`. 
**🔴 Anti-pattern**: `if User.objects.filter(is_active=True):` (loads entire table into memory).
**✅ Fix**: `if User.objects.filter(is_active=True).exists():`

## 9. Dataclasses and Typing
Django 3.2+ and especially 4.0+ heavily support type hints. Dataclasses are excellent for passing data across the service layer.

```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass(frozen=True, slots=True)
class PaymentContext:
    user_id: int
    amount: float
    currency: str
    discount_codes: List[str]
```
Use Dataclasses for domain logic that doesn't need to be persisted to DB immediately. Use Django Models only when defining database schema and ORM operations.

## Production Checklist
- [ ] All custom decorators use `@functools.wraps`
- [ ] Model `__str__` methods do not trigger N+1 database queries
- [ ] Large queryset iterations use `.iterator()`
- [ ] Typing is enforced on Service layer boundaries using Dataclasses/Pydantic


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
The Advanced Python exists to solve complex engineering problems in the Django ecosystem. Without it, the application would suffer from tight coupling, lack of scalability, and poor developer ergonomics.

## 2. Django Internal Source Traces

Let's dive into how Advanced Python actually works under the hood in Django 6.1+.

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

## 5. 3:00 AM Production Incident: Advanced Python Failure

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
def test_advanced_python_edge_case(client, mocker):
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
