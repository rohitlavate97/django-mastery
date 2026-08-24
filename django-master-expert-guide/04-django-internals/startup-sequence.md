# Django Startup Sequence Internals [DJANGO 6.1+]

## 1. Mental Model
```text
[WSGI/ASGI Server] 
      | (Imports wsgi.py/asgi.py)
      v
+------------------------------------------+
| os.environ.setdefault('DJANGO_SETTINGS') |
| django.setup()                           |
+------------------------------------------+
      |
      v
[1. Configuration Loading (Settings)]
      | (Loads global_settings.py + user settings)
      v
[2. App Registry Initialization]
      | -> app_config.create()
      | -> app_config.ready()  <-- User Code Execution
      v
[3. Model Loading]
      | -> populate() apps & models
      v
[4. URL Configuration Loading]
      | (Delayed/Lazy until first request)
      v
[Ready to Handle Requests]
```

## 2. Why It Exists
Django needs a strict two-phase initialization to resolve complex dependencies (like models defining foreign keys to other apps before those apps are loaded) without circular imports.

## 3. Internal Working
Trace of `django/core/wsgi.py` and `django/__init__.py`:
```python
# django/__init__.py
def setup(set_prefix=True):
    from django.apps import apps
    from django.conf import settings
    from django.utils.log import configure_logging

    configure_logging(settings.LOGGING_CONFIG, settings.LOGGING)
    if set_prefix:
        set_script_prefix(
            '/' if settings.FORCE_SCRIPT_NAME is None else settings.FORCE_SCRIPT_NAME
        )
    apps.populate(settings.INSTALLED_APPS)
```
`apps.populate()` works in 3 stages:
1. Loads all `AppConfig` classes.
2. Imports `models.py` for all apps.
3. Runs `AppConfig.ready()`.

## 4. Basic Implementation
```python
# apps.py
from django.apps import AppConfig

class UsersConfig(AppConfig):
    name = 'users'

    def ready(self):
        import users.signals  # Signal registration
```

## 5. Production-Ready Implementation
```python
# apps.py
import logging
from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

class PaymentConfig(AppConfig):
    name = 'payment'
    verbose_name = "Payment Gateway"

    def ready(self):
        try:
            from . import signals, webhooks
            from django.conf import settings
            
            if not hasattr(settings, 'STRIPE_API_KEY'):
                raise ImproperlyConfigured("STRIPE_API_KEY must be set in production")
                
            logger.info("Payment app initialized successfully.")
        except ImportError as e:
            logger.error("Failed to load payment dependencies", exc_info=True)
            raise
```

## 6. Anti-Patterns
🔴 **TICKING TIME BOMB**: Database queries in `AppConfig.ready()`.
```python
# BROKEN - Will crash collectstatic, makemigrations, etc.
class AnalyticsConfig(AppConfig):
    def ready(self):
        from .models import Metric
        # NEVER DO THIS: DB might not exist or migrations pending!
        Metric.objects.create(name="startup") 
```

## 7. Environment-Specific Behavior
| Environment | Startup Behavior |
|-------------|------------------|
| Local Dev | Runs twice if auto-reload is enabled (Main process + worker thread). |
| Docker | Startup time critical. `collectstatic` should be done in build, not runtime. |
| CI | Often runs headless; DB connection must be mocked or available instantly. |
| 100k RPS Prod | Pre-fork workers (e.g. `gunicorn -w 4 --preload`) load models into shared memory before fork. |

## 8. Local Development Issues
🔴 SYMPTOM: `AppRegistryNotReady: Apps aren't loaded yet.`
🔍 CAUSE: Importing models at the root level of `__init__.py` or `apps.py`.
🔧 FIX: Move the model import inside a function or the `ready()` method.

## 9. Production Issues
INCIDENT: Memory Exhaustion during Gunicorn worker boot.
SEVERITY: High
CAUSE: A heavy machine learning model was loaded in `AppConfig.ready()` on a 4-worker Gunicorn setup without `--preload`. Each worker loaded a separate 1GB model, OOM killing the container.
FIX: Use `gunicorn --preload` to load it in the master process and share memory, or better, move ML loading to a separate microservice.

## 10. Failure Simulation
Intentionally create a circular dependency:
```python
# app1/models.py
from app2.models import ModelB

# app2/models.py
from app1.models import ModelA
```
Use pytest to catch this:
```python
def test_app_starts():
    from django.core.management import call_command
    # This will fail if there are circular imports during model load
    call_command('check')
```

## 11. Decision Matrix
| Logic Location | Pros | Cons |
|----------------|------|------|
| `AppConfig.ready()` | Guaranteed to run once per process | Easy to cause circular imports |
| `urls.py` | Good for URL specific setup | Runs lazily on first request |
| Middleware `__init__` | Runs at server start | Only runs if middleware is active |

## 12. Senior-Level Questions
**Q: How do you safely run code only exactly once on server start in a multi-worker environment?**
A: You cannot reliably do it in `ready()` if you have multiple workers. Use a distributed lock (Redis) or run a custom Django management command before starting Gunicorn.

## 13. Production Checklist
- [ ] No DB queries in `ready()`.
- [ ] `gunicorn --preload` evaluated for memory savings.
- [ ] Startup checks passing via `python manage.py check --deploy`.
