# Django Lazy Objects Internals [DJANGO 6.1+]

## 1. Mental Model
```text
[ request.user (SimpleLazyObject) ] 
       | (attribute access: .username)
       v
  __getattr__ intercepted!
       |
  [ Evaluates wrapped function (e.g. get_user) ]
       |
  [ Replaces itself internally with real User object ]
       |
[ Returns "admin" ]
```

## 2. Why It Exists
Defers expensive operations (like DB queries to fetch the User session, or translating strings) until the exact moment the value is actually needed. If it's never needed, the cost is avoided entirely.

## 3. Internal Working
Trace of `django/utils/functional.py`:
```python
class LazyObject:
    _wrapped = None

    def __init__(self):
        self._wrapped = empty

    def _setup(self):
        raise NotImplementedError

    def __getattr__(self, name):
        if self._wrapped is empty:
            self._setup()
        return getattr(self._wrapped, name)

class SimpleLazyObject(LazyObject):
    def __init__(self, func):
        self._wrapped = empty
        self.__dict__['_setupfunc'] = func

    def _setup(self):
        self._wrapped = self._setupfunc()
```

## 4. Basic Implementation
```python
from django.utils.functional import SimpleLazyObject

def expensive_computation():
    print("Calculating...")
    return 42

lazy_val = SimpleLazyObject(expensive_computation)
# "Calculating..." is NOT printed yet
```

## 5. Production-Ready Implementation
```python
# How Django's AuthenticationMiddleware uses it:
from django.utils.functional import SimpleLazyObject
from django.contrib.auth import get_user

class CustomAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # We don't fetch the user from DB yet!
        request.user = SimpleLazyObject(lambda: get_user(request))
        return self.get_response(request)
```

## 6. Anti-Patterns
🔴 **TICKING TIME BOMB**: Serializing Lazy Objects.
```python
import json
# BROKEN: json module doesn't know how to handle SimpleLazyObject
json.dumps({'user': request.user}) # Raises TypeError
```

## 7. Environment-Specific Behavior
Identical across environments. Used heavily in Internationalization (`gettext_lazy`) which affects memory footprint slightly (caching lazy translation strings).

## 8. Local Development Issues
🔴 SYMPTOM: `TypeError: Object of type SimpleLazyObject is not JSON serializable`
🔍 CAUSE: Passing `request.user` or `_('String')` directly to `JsonResponse` or `json.dumps`.
🔧 FIX: Cast to string/id (`str(request.user)`, `request.user.id`) or force evaluation.

## 9. Production Issues
INCIDENT: Unnecessary DB queries in API endpoints.
SEVERITY: Medium
CAUSE: A middleware logged `request.user.id` on *every* request, forcing the lazy object to evaluate and hit the DB, even for public API endpoints that didn't need auth.
FIX: Change logging to only record the user ID if `request.user.is_authenticated` without triggering full fetch, or move logging to after view execution where it might already be fetched.

## 10. Failure Simulation
```python
def test_lazy_evaluation_timing():
    evaluated = False
    def setup():
        nonlocal evaluated
        evaluated = True
        return "result"
        
    lazy = SimpleLazyObject(setup)
    assert not evaluated
    _ = lazy.upper()
    assert evaluated
```

## 11. Decision Matrix
| Tool | Use Case |
|------|----------|
| `SimpleLazyObject` | Deferring DB queries/heavy logic on Request objects. |
| `lazy()` | Deferring function calls (like reverse URLs in forms). |
| `gettext_lazy()` | Translating strings at render time, not import time. |

## 12. Senior-Level Questions
**Q: How do you check if a `SimpleLazyObject` has been evaluated without triggering evaluation?**
A: You can inspect `lazy_obj._wrapped`. If it equals `django.utils.functional.empty`, it hasn't been evaluated yet.

## 13. Production Checklist
- [ ] Lazy objects are not passed directly to external libraries (Celery, JSON, Redis).
- [ ] DB calls are truly deferred (avoid triggering them in early middleware if not needed).
