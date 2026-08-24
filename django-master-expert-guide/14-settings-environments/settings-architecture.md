# Django Settings Architecture: A Staff Engineer's Guide [DJANGO 6.1+]

## 1. Mental Model: The Settings Pipeline

Django's settings module is not just a file; it's a runtime singleton evaluated at boot time. Managing settings across environments requires a layered, explicit architecture.

```text
+-------------------+      +-------------------+      +--------------------+
|                   |      |                   |      |                    |
|  OS Environment   |----->|  .env File / Vault|----->| settings/base.py   |
|  Variables        |      |  (Secrets)        |      | (Shared defaults)  |
|                   |      |                   |      |                    |
+-------------------+      +-------------------+      +--------------------+
                                                             |
                                                             v
+-------------------+      +-------------------+      +--------------------+
|                   |      |                   |      |                    |
| settings/prod.py  |<-----| settings/local.py |<-----|  DJANGO_SETTINGS_  |
| (Overrides)       |      | (Overrides)       |      |  MODULE env var    |
|                   |      |                   |      |                    |
+-------------------+      +-------------------+      +--------------------+
```

### Components Detailed
- **`DJANGO_SETTINGS_MODULE`**: The entry point. Tells Django which Python module to load (e.g., `config.settings.production`).
- **`base.py`**: Contains 90% of your settings. Always checked into version control.
- **Environment Variables**: Overrides for secrets, hostnames, and environment-specific toggles (e.g., `DATABASE_URL`).
- **Vault/Secret Manager**: In prod, secrets are injected at runtime, never stored in files.

---

## 2. Why It Exists (The Configuration Drift Problem)

If you only use a single `settings.py` file, you will end up with brittle `if DEBUG:` statements scattered everywhere. 
- You might accidentally enable a production email backend in local dev, spamming real users.
- You might leak API keys into version control.
- Your CI pipeline might fail because it tries to connect to a local PostgreSQL instance that doesn't exist in GitHub Actions.

---

## 3. Internal Working: Tracing Settings Boot

When you run `manage.py runserver` or Gunicorn boots:

1. **`django.conf.__init__.py`**: Django initializes the `LazySettings` object.
2. It reads the `DJANGO_SETTINGS_MODULE` environment variable.
3. It imports that module dynamically.
4. It iterates through all uppercase variables in that module and stores them in memory.
5. Once accessed for the first time, `LazySettings` evaluates and caches the values. You *cannot* safely change settings at runtime after boot.

---

## 4. Basic Implementation vs. Production Implementation

### ❌ The Broken/Basic Way (Ticking Time Bomb)

```python
# settings.py (Monolithic file)
import os

# 🚨 DANGER 1: Hardcoded secrets in version control
SECRET_KEY = 'django-insecure-my-super-secret-key-that-is-on-github'

# 🚨 DANGER 2: Environment detection via DEBUG flag
DEBUG = True

if DEBUG:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': 'db.sqlite3',
        }
    }
else:
    # 🚨 DANGER 3: Prod DB credentials checked into Git
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'prod_db',
            'USER': 'postgres',
            'PASSWORD': 'password123', 
        }
    }
```

### ✅ The Production-Hardened Way (django-environ)

```python
# config/settings/base.py
from pathlib import Path
import environ
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 🔧 FIX: Strict typing and casting for env vars
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, [])
)

# 🔧 FIX: Read .env only if it exists (local dev), prod gets vars from OS
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# Core Settings
SECRET_KEY = env('DJANGO_SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS')

# Database
# Uses dj-database-url format: postgres://user:pass@host:port/dbname
DATABASES = {
    'default': env.db('DATABASE_URL')
}
```

```python
# config/settings/production.py
from .base import *  # noqa
import sentry_sdk

# 🔧 FIX: Force HTTPS in production
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# 🔧 FIX: Strict Host checking
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=['api.mycompany.com'])

# 🔧 FIX: Prod Monitoring
sentry_sdk.init(
    dsn=env('SENTRY_DSN'),
    environment="production",
    traces_sample_rate=0.1,
)
```

---

## 5. Production Incident: The PII Local Leak

### 🔴 INCIDENT: Staging Emails Sent to Real Users
**Severity:** SEV-1
**Symptoms:** Real users started receiving dummy "Test Order" confirmation emails with bizarre data.
**Investigation:** 
- Checked SendGrid logs: Emails originated from the staging server IP.
- Checked `config/settings/staging.py`.
**Root Cause:**
A developer added a new `EMAIL_BACKEND` configuration to `base.py` but forgot to override it in `staging.py`. Staging fell back to `base.py`, which defaulted to the SendGrid production API key defined in the staging environment variables (which had been copy-pasted from prod).
**🔧 FIX & Prevention:**
1. Separated API keys explicitly by environment in AWS Parameter Store.
2. Forced a `DummyBackend` for emails if `ENVIRONMENT != 'production'`.
```python
# config/settings/base.py
ENVIRONMENT = env('ENVIRONMENT', default='local')

if ENVIRONMENT == 'production':
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

---

## 6. Environment Comparison Matrix

| Variable | Local (`.env`) | CI (GitHub Actions) | Staging | Production |
| :--- | :--- | :--- | :--- | :--- |
| **`DJANGO_SETTINGS_MODULE`** | `config.settings.local` | `config.settings.test` | `config.settings.production` | `config.settings.production` |
| **`DEBUG`** | `True` | `False` | `False` | `False` |
| **`DATABASE_URL`** | `postgres://...` (Docker) | `postgres://...` (Service) | Secret Manager | Secret Manager |
| **`EMAIL_BACKEND`** | `console` | `locmem` | `console` | `smtp` / `Anymail` |

---

## 7. Pytest Test Suite for Settings Validation

```python
# tests/test_settings.py
import pytest
from django.conf import settings
import os

def test_production_settings_are_secure():
    # Only run this test if we are testing prod settings
    if os.environ.get('DJANGO_SETTINGS_MODULE') == 'config.settings.production':
        assert settings.DEBUG is False
        assert settings.SECURE_SSL_REDIRECT is True
        assert settings.SESSION_COOKIE_SECURE is True
        assert settings.CSRF_COOKIE_SECURE is True
        
        # Ensure we don't accidentally use sqlite in prod
        assert 'postgresql' in settings.DATABASES['default']['ENGINE']

def test_no_hardcoded_secret_key():
    assert 'django-insecure' not in settings.SECRET_KEY
```
