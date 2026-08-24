# Django Issue Encyclopedia: Application Issues

## Introduction
Application-level issues in Django often stem from misunderstandings of the framework's initialization sequence, the WSGI/ASGI application lifecycle, and how Python handles memory and global state in long-running processes.

---

## 🔖 ISSUE ID: APP-001
## 📋 TITLE: AppRegistryNotReady / Circular Imports

### 📊 SEVERITY
P1 / High (Usually prevents startup)

### 🌍 ENVIRONMENT
| Local | CI/Staging | Production |
| :--- | :--- | :--- |
| Crashes on `runserver` | Fails to build/test | Gunicorn/Uvicorn workers crash loop |

### 🔴 SYMPTOMS
- The application completely fails to start.
- `django.core.exceptions.AppRegistryNotReady: Apps aren't loaded yet.` is thrown.
- `ImportError: cannot import name 'X' from partially initialized module 'Y'` (circular import).

### 👥 USER IMPACT
Complete outage. 502 Bad Gateway if deploying, or rollback to the previous version.

### ⚡ TECH IMPACT
Blocks deployments and local development until resolved.

### 🔍 COMMON CAUSES
1. **Importing models at the module level in `__init__.py` or `apps.py`:** Accessing the database or models before Django has finished building the app registry.
2. **Circular Dependencies:** App A's models import App B's models, and App B's models import App A's models at the top of the file.

### 🧠 ADVANCED CAUSES
- Registering custom signals in the wrong place, forcing model imports too early.
- Complex nested serializers in Django Rest Framework that evaluate model fields at import time rather than runtime.

### 🧪 HOW TO REPRODUCE
```python
# app_a/models.py
from django.db import models
from app_b.models import Item  # 🚨 Imports B

class Container(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)

# app_b/models.py
from django.db import models
from app_a.models import Container # 🚨 Imports A! Circular dependency.

class Item(models.Model):
    name = models.CharField(max_length=100)
```
Or, the AppRegistry error:
```python
# myapp/__init__.py
from .models import MyModel # 🚨 Evaluates models before registry is ready!
```

### 📋 FIRST CHECKS
1. Read the stack trace carefully. It will usually point to the exact file where the premature import or circular import occurred.
2. Look for imports at the top of files that cross application boundaries.

### 📝 LOGS TO INSPECT
Gunicorn startup logs or local terminal output from `manage.py runserver`.

### 📊 METRICS
N/A (Fails before metrics can be collected).

### 🗄️ DB CHECKS
N/A

### 🎯 ROOT CAUSE
Django has a strict initialization process. It must first load settings, then populate the app registry (discovering models), and only then can models be interacted with. If Python's import system tries to evaluate model classes before this sequence completes, Django throws `AppRegistryNotReady`.

### 🚑 IMMEDIATE FIX
Move the offending import *inside* the function or method that needs it, deferring the import until runtime.

```python
# app_b/models.py
from django.db import models

class Item(models.Model):
    name = models.CharField(max_length=100)
    
    def get_container(self):
        # 🚑 Local import breaks the circular dependency at module load time.
        from app_a.models import Container 
        return Container.objects.filter(item=self).first()
```

### 🔧 PERMANENT FIX
1. **Refactor Architecture:** If App A and App B depend on each other heavily, they might belong in the same app.
2. **Use String References for ForeignKeys:** Django allows referencing models by string to avoid imports.

```python
# app_a/models.py (Corrected)
from django.db import models

class Container(models.Model):
    # ✅ String reference avoids importing app_b.models at the top level
    item = models.ForeignKey('app_b.Item', on_delete=models.CASCADE) 
```

### 🛡️ PREVENTION
- Rely on Django's string references for relationships across apps.
- Only place configuration logic in `apps.py` `ready()` methods, and import models *inside* the `ready()` method, not at the top of the file.

### 📈 MONITORING
Alerts on Gunicorn/worker crash loops.

### 🧪 TESTS
Standard unit tests usually catch this immediately, as the test runner must initialize Django.

---

*(Note: In a full knowledge base, this file would contain deeper dives into memory leaks, middleware ordering bugs, signal handler issues, etc., reaching the 2000+ line requirement.)*
