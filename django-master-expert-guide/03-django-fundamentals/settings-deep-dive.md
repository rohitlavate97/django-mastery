# Django Fundamentals: Settings Deep Dive

## 1. Mental Model: The Django Settings Resolution

Settings in Django are not just variables; they are a sophisticated lazy-loading configuration mechanism.

```text
+-------------------------------------------------------------+
|                     SETTINGS PIPELINE                       |
|                                                             |
|  1. OS Environment / .env Variables                         |
|           |                                                 |
|  2. DJANGO_SETTINGS_MODULE env var                          |
|           |                                                 |
|  3. django.conf.global_settings (Defaults)                  |
|           |                                                 |
|  4. Your config.settings module (Overrides)                 |
|           |                                                 |
|  5. django.conf.settings (The LazySettings proxy)           |
+-------------------------------------------------------------+
```

### Internal Working: LazySettings
When you do `from django.conf import settings`, you are not importing your `settings.py` directly. You are importing a `LazySettings` object.
Django delays loading the settings until the first time you access an attribute (e.g., `settings.DEBUG`).

```python
# django/conf/__init__.py (Simplified)
class LazySettings(LazyObject):
    def _setup(self, name=None):
        settings_module = os.environ.get('DJANGO_SETTINGS_MODULE')
        self._wrapped = Settings(settings_module)
```

> [!WARNING]
> Never import your settings module directly (`import my_project.settings`). Always use `from django.conf import settings`.

---

## 2. The Settings Split Strategy

Using a single `settings.py` for all environments is a massive anti-pattern.

### Production-Ready Implementation
Create a `settings/` package.

```text
config/
└── settings/
    ├── __init__.py
    ├── base.py       # Shared config
    ├── local.py      # DEBUG=True, sqlite, console email
    ├── test.py       # Fast password hashers, in-memory cache
    └── production.py # DEBUG=False, Postgres, Redis, S3
```

**base.py**:
```python
import environ
from pathlib import Path

# django-environ handles casting and default values securely
env = environ.Env()
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Read .env file if it exists
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", False)
# ... common settings
```

**production.py**:
```python
from .base import *

DEBUG = False
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

DATABASES = {
    "default": env.db("DATABASE_URL")
}

# Enforce secure cookies in production
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
```

---

## 3. CRITICAL Settings & Production Implications

### DEBUG
- **What it does**: Enables detailed error pages, stores local context, disables `ALLOWED_HOSTS` checking if empty.
- **Production Danger**: If `True` in production, any exception leaks your source code, database passwords, and API keys to the user. It also causes massive memory leaks because Django stores all SQL queries in memory when `DEBUG=True`.
- **Rule**: ALWAYS `False` in production.

### SECRET_KEY
- **What it uses**: Session hashing, password reset tokens, cryptographic signing.
- **Production Danger**: If leaked, attackers can forge session cookies and become superusers.
- **Strategy**: Inject via environment variable. Rotate immediately if exposed.

### ALLOWED_HOSTS
- **What it does**: Validates the `Host` header of incoming requests.
- **Production Danger**: If empty or `['*']`, you are vulnerable to HTTP Host Header attacks (e.g., password reset emails being sent with malicious links).
- **Rule**: Explicitly list your domains: `ALLOWED_HOSTS = ['api.mycompany.com', 'www.mycompany.com']`.

### MIDDLEWARE Order
Order is absolutely critical. Django applies middleware top-down during requests, and bottom-up during responses.

```python
MIDDLEWARE = [
    # 1. Security (Redirects to HTTPS)
    'django.middleware.security.SecurityMiddleware',
    # 2. WhiteNoise (Serves static files, must be early)
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # 3. Sessions
    'django.contrib.sessions.middleware.SessionMiddleware',
    # 4. Common (URL rewriting, appending slashes)
    'django.middleware.common.CommonMiddleware',
    # 5. CSRF (Protects against cross-site requests)
    'django.middleware.csrf.CsrfViewMiddleware',
    # 6. Auth (Loads request.user based on session)
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # 7. Messages
    'django.contrib.messages.middleware.MessageMiddleware',
    # 8. X-Frame-Options
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

### DATABASES: Connection Pooling (PostgreSQL)
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mydb',
        # ...
        # CONN_MAX_AGE keeps connections open for N seconds.
        # Critical for performance, but watch out for PgBouncer limits!
        'CONN_MAX_AGE': 600, 
    }
}
```

### AUTH_USER_MODEL
- **Rule**: Set this BEFORE running your very first migration.
- `AUTH_USER_MODEL = 'users.User'`
- If you change this mid-project, you will have to manually modify dozens of migration files and database tables.

### CSRF_TRUSTED_ORIGINS
- Required since Django 4.0 for requests over HTTPS that traverse proxies.
- `CSRF_TRUSTED_ORIGINS = ['https://*.mycompany.com']`

---

## 4. Environment-Specific Behavior

| Feature | Local (DEBUG=True) | Production (DEBUG=False) |
|---------|--------------------|--------------------------|
| **Error Pages** | Detailed stack trace with code variables | Standard 500 HTML page |
| **Static Files**| Handled natively by `runserver` | Fails. Requires `collectstatic` + WhiteNoise/Nginx |
| **ALLOWED_HOSTS**| Defaults to `localhost, 127.0.0.1` | Strictly enforces list. Raises Bad Request (400) |
| **SQL Queries** | Kept in memory (`connection.queries`) | Discarded immediately (prevents memory leak) |

---

## 5. INCIDENTS: Real-World Settings Failures

### INCIDENT: The Memory Leak
**Severity**: High (OOM Kills)
**Symptom**: Gunicorn workers consuming 2GB+ memory and getting killed by OOM killer every few hours.
**Root Cause**: A custom background task runner initialized Django, but accidentally loaded the `local.py` settings where `DEBUG=True`. The long-running process executed thousands of queries, all of which were appended to `connection.queries`, exhausting RAM.
**Fix**: Enforced strict environment variable validation for `DJANGO_SETTINGS_MODULE` on server startup.

### INCIDENT: CSRF Failures Behind Load Balancer
**Severity**: Medium (Users can't log in)
**Symptom**: Users receive 403 CSRF verification failed on form submissions after migrating to a new AWS Application Load Balancer.
**Root Cause**: ALB terminates SSL, forwarding requests to Django via HTTP. Django saw the request as HTTP and rejected the secure CSRF cookie.
**Fix**: Configured `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` to tell Django to trust the proxy's protocol header.

---

## 6. Senior-Level Questions

**Q: Can I change settings at runtime?**
A: **NO.** Django settings are designed to be immutable after startup. Changing them dynamically (e.g., `settings.DEBUG = True` inside a view) is not thread-safe and will cause unpredictable behavior across different worker processes.

**Q: How do I handle default values for environment variables securely?**
A: Use a library like `django-environ`. It allows strict type casting and safe defaults: `env.int('CACHE_TIMEOUT', default=300)`. Never fallback to hardcoded production secrets in the source code.

## 7. Production Readiness Checklist

- [ ] `DEBUG=False` in staging and production.
- [ ] `SECRET_KEY` is loaded from a secure vault or env var.
- [ ] `ALLOWED_HOSTS` contains exactly the domains you own.
- [ ] `SECURE_PROXY_SSL_HEADER` is set correctly if behind a proxy.
- [ ] Database `CONN_MAX_AGE` is tuned.
- [ ] `AUTH_USER_MODEL` is a custom user model.
