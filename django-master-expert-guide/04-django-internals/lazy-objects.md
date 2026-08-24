# Lazy Objects in Django

## 1. Mental Model
```text
LazyObject (Proxy) ---> [Not evaluated yet]
       |
     __str__ / __getattr__ triggered
       |
       v
   Evaluates target
       |
       v
Returns Real Object Result
```

## 2. Why It Exists
Lazy evaluation delays execution until the result is strictly required. This is essential for:
1. Translating strings before the language is known (`gettext_lazy`).
2. Avoiding circular imports in `settings`.
3. Database performance (Lazy QuerySets).

## 3. Internal Working
`SimpleLazyObject` uses a setup function. It overrides special methods like `__getattr__`, `__str__`, etc. When these are called, it checks if `_wrapped` is set. If not, it calls the setup function.

## 4. Basic Implementation
```python
from django.utils.translation import gettext_lazy as _

class MyModel(models.Model):
    # Evaluated only when rendered in a form or template
    name = models.CharField(verbose_name=_("Name"))
```

## 5. Production-Ready Implementation
```python
from django.utils.functional import SimpleLazyObject

def get_expensive_config():
    # some heavy database/network call
    return {"key": "value"}

# Delays execution until 'config' is actually accessed
config = SimpleLazyObject(get_expensive_config)
```

## 6. Anti-Patterns
🔴 **TICKING TIME BOMB**: Serializing lazy objects.
```python
# INCORRECT
import json
from django.utils.translation import gettext_lazy as _

data = {"msg": _("Hello")}
# json.dumps(data)  # TypeError: Object of type __proxy__ is not JSON serializable
```

## 7. Environment-Specific Behavior
Lazy translation strings behave differently in testing if the language is forced via `override_settings(LANGUAGE_CODE='fr')`.

## 8. Local Development Issues
🔴 SYMPTOM: `TypeError: Object of type __proxy__ is not JSON serializable`
🔍 CAUSE: Trying to pass a `gettext_lazy` string to a JSON encoder.
🔧 FIX: Force evaluation by wrapping in `str()` before serializing.

## 9. Production Issues
INCIDENT: High memory usage.
SEVERITY: Medium
CAUSE: QuerySets were being fully evaluated into massive lists in memory by calling `list(queryset)` unnecessarily.
FIX: Rely on QuerySet laziness. Iterate directly over the QuerySet or use `.iterator()`.

## 10. Failure Simulation
```python
# Evaluating a QuerySet too early
qs = User.objects.all()
# Doing len(qs) executes SELECT COUNT(*) or loads all into memory
length = len(qs)
```

## 11. Decision Matrix
| Use Case | Solution |
|----------|----------|
| Translation in models.py | `gettext_lazy` |
| Translation in views.py | `gettext` |
| Expensive property | `cached_property` |

## 12. Senior-Level Questions
**Q: How does `request.user` work?**
A: `AuthenticationMiddleware` assigns a `SimpleLazyObject` to `request.user`. The database is only queried for the user if you actually access `request.user.id` or another attribute in the view.

## 13. Production Checklist
- [ ] Never use `gettext_lazy` inside an Exception message that goes to a logger.
- [ ] Understand when QuerySets evaluate (slicing vs iteration).
