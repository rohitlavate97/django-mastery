# Django Startup Sequence Deep Dive

## 1. Mental Model
```text
[ WSGI / ASGI / manage.py ]
         |
         v
 os.environ.setdefault()
         |
         v
   django.setup()  <-- The Core Initialization
         |
         +--> configure_logging()
         |
         +--> apps.populate(INSTALLED_APPS)
               |
               +--> Phase 1: AppConfig.create() (Load app configs)
               |
               +--> Phase 2: import_models() (Load all models.py)
               |
               +--> Phase 3: ready() (Run AppConfig.ready())
         |
         v
  [ Django Ready ]
```

## 2. Why It Exists
The startup sequence ensures that all configuration, models, and apps are loaded exactly once and in the correct order before any requests are served. It solves the problem of circular imports and missing references.

## 3. Internal Working (django.apps.registry.Apps.populate)
When `django.setup()` is called, it triggers `apps.populate()`. This happens in 3 distinct phases to prevent circular dependencies:
1. **Load AppConfigs**: Django creates `AppConfig` instances for all apps.
2. **Import Models**: Django imports the `models.py` of each app. This registers all models in the `AppRegistry`.
3. **Run ready()**: Django calls the `ready()` method on every `AppConfig`. This is where signals should be connected.

## 4. Basic Implementation
```python
# apps.py
from django.apps import AppConfig

class MyAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'my_app'

    def ready(self):
        # Implicitly connect signals
        import my_app.signals
```

## 5. Production-Ready Implementation
```python
# apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class PaymentAppConfig(AppConfig):
    name = 'payments'
    verbose_name = 'Payment Processing'

    def ready(self):
        try:
            import payments.signals  # noqa
            # Avoid database access here!
            logger.info("Payment app initialized successfully.")
        except ImportError as e:
            logger.error(f"Failed to load payment signals: {e}")
            raise
```

## 6. Anti-Patterns
🔴 **TICKING TIME BOMB**: Database queries in `AppConfig.ready()`
```python
# INCORRECT
def ready(self):
    from .models import Config
    # If migrations haven't run, this will crash the startup!
    if Config.objects.filter(active=True).exists():
        pass
```

## 7. Environment-Specific Behavior
| Environment | Behavior |
|-------------|----------|
| Local (runserver) | Runs setup twice (once for the main process, once for the reloader). |
| Docker | Gunicorn prefork model means setup runs in the master, and optionally per worker. |
| Production | Gunicorn with `preload_app=True` runs setup once in master, saving RAM. |

## 8. Local Development Issues
🔴 SYMPTOM: `django.core.exceptions.AppRegistryNotReady: Apps aren't loaded yet.`
🔍 CAUSE: Trying to import models at the module level in `__init__.py` or `apps.py` before `django.setup()` finishes.
🔧 FIX: Move the model import inside the `ready()` method or a function.

## 9. Production Issues
INCIDENT: Gunicorn workers crashing on boot.
SEVERITY: High
CAUSE: Code in `AppConfig.ready()` was hitting the database, but the database connection was dropping or migrations hadn't run during a deployment.
FIX: Defer DB access. Use `post_migrate` signal if DB initialization is required.

## 10. Failure Simulation
To intentionally crash startup:
```python
# In your settings.py
import django
from django.conf import settings
# Accessing apps before setup
from django.apps import apps 
apps.get_models() # Crashes!
```

## 11. Decision Matrix
| Feature | When to use |
|---------|-------------|
| `AppConfig.ready()` | Signal registration, non-DB initialization. |
| `post_migrate` signal | Initializing database rows after migrations. |

## 12. Senior-Level Questions
**Q: Why does Django have 3 phases for app loading?**
A: To solve circular imports. If App A's models import App B's models, both apps need their `AppConfig` loaded first. By separating config loading from model importing, Django ensures the registry knows about all apps before models start cross-referencing each other.

## 13. Production Checklist
- [ ] No database access in `ready()`.
- [ ] All signals imported in `ready()`.
- [ ] `default_auto_field` is explicitly set.
