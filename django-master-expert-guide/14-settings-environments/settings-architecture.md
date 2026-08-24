# Django Settings Architecture: The Split Settings Pattern

## 1. Mental Model
```text
+---------------------+
|   Environment       |
|   (OS/Docker)       |
+---------+-----------+
          |
          v (Env Vars)
+---------+-----------+       +-------------------+       +-------------------+
| base.py             |<------| development.py    |       | test.py           |
| (Common defaults)   |       | (Local overrides) |       | (Fast execution)  |
+---------+-----------+       +-------------------+       +-------------------+
          ^
          |
+---------+-----------+       +-------------------+
| staging.py          |       | production.py     |
| (Pre-prod config)   |       | (Secure/Optimized)|
+---------------------+       +-------------------+
```

## 2. Why It Exists
Monolithic `settings.py` files become an unmaintainable mess of `if DEBUG:` statements. This violates the 12-Factor App methodology by hardcoding environment-specific logic into the application code. A split settings architecture isolates configuration per environment, reducing the risk of deploying development settings (like `DEBUG = True`) to production.

## 3. Internal Working
When Django starts, it looks for the `DJANGO_SETTINGS_MODULE` environment variable. 
By setting this variable to `project.settings.production`, Django loads `production.py`.
In a split setup, `production.py` starts by doing `from .base import *`, pulling in all base configurations, and then overrides or adds production-specific configurations.

## 4. Basic Implementation
`project/settings/base.py`:
```python
import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent.parent

INSTALLED_APPS = ['django.contrib.admin', ...]
MIDDLEWARE = [...]
ROOT_URLCONF = 'project.urls'
```

`project/settings/development.py`:
```python
from .base import *

DEBUG = True
SECRET_KEY = 'django-insecure-dev-key'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

## 5. Production-Ready Implementation
`project/settings/production.py`:
```python
from .base import *
import environ

env = environ.Env()

DEBUG = False
SECRET_KEY = env('DJANGO_SECRET_KEY')

ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=['example.com'])

DATABASES = {
    'default': env.db('DATABASE_URL')
}

# Security settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:**
```python
# settings.py
import os
if os.environ.get('ENV') == 'production':
    DEBUG = False
else:
    DEBUG = True
```
*Why it's bad:* Creates a fragile monolithic settings file. Any import error inside the `if` block could cause a fallback to development settings in production.

## 7. Environment-Specific Behavior
| Feature | Local | Staging | Production |
|---------|-------|---------|------------|
| DEBUG   | True  | False   | False      |
| Caching | Dummy | Redis   | Redis (Cluster) |
| Emails  | Console | SMTP (Test) | SMTP (Prod) |

## 8. Local Development Issues
🔴 SYMPTOM: `ModuleNotFoundError: No module named 'project.settings'`
🔍 CAUSE: `DJANGO_SETTINGS_MODULE` is not set or points to a non-existent file.
🔧 FIX: Set `export DJANGO_SETTINGS_MODULE=project.settings.development` in your `.bashrc` or virtualenv `activate` script.

## 9. Production Issues
🔴 INCIDENT: Production Database Overwritten
- **Severity:** CRITICAL
- **Investigation:** Developer ran `./manage.py migrate` locally but `DJANGO_SETTINGS_MODULE` was accidentally set to production.
- **Root Cause:** Lack of strict environment isolation and shared credentials.
- **Fix:** Restrict database access by IP, and ensure `production.py` enforces connection over SSL/VPC only.

## 10. Failure Simulation
To test the split settings, unset `DJANGO_SETTINGS_MODULE` and run `python manage.py check`. Django should fail to start, proving it relies completely on explicitly defined environments.

## 11. Decision Matrix
| Pattern | Pros | Cons | Use Case |
|---------|------|------|----------|
| Split Settings (`base.py`, etc) | Clean, explicit | Requires module setup | Mid-to-Large projects |
| Monolithic + Env Vars | Simple | Can get messy | Small projects |
| Dynamic Loader (Dynaconf) | Powerful | Black magic | Microservices |

## 12. Senior-Level Questions
**Q: How does `from .base import *` affect Python namespace pollution?**
A: It imports everything from `base.py` into the current namespace. While generally discouraged in standard Python (PEP 8), it is an accepted idiom in Django split settings to simulate a single configuration file. Tools like `flake8` might complain, which is why `# noqa: F403` is often appended.

## 13. Production Checklist
- [ ] `DJANGO_SETTINGS_MODULE` defaults to `development` or errors out if not set.
- [ ] `production.py` does not provide defaults for secrets (e.g., `SECRET_KEY`).
- [ ] All security settings (`SECURE_HSTS_SECONDS`, etc.) are explicitly defined in `production.py`.
