# Environment Variables in Django

## 1. Mental Model
```text
[OS Environment / .env File]
         | (1. Read)
         v
[django-environ (Schema & Validation)]
         | (2. Parse & Cast)
         v
[Django settings.py]
         | (3. Apply)
         v
[Django Application]
```

## 2. Why It Exists
Storing configuration in the environment separates configuration from code (12-Factor App). It allows the same code bundle to be deployed across multiple environments (Dev, Staging, Prod) without modification, relying solely on environment variables to change behavior.

## 3. Internal Working
Libraries like `django-environ` read the OS environment variables (and optionally a `.env` file). They cast strings to Python types (booleans, integers, lists) based on a defined schema.

## 4. Basic Implementation
```python
import environ
import os

env = environ.Env(
    DEBUG=(bool, False)
)

environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

DEBUG = env('DEBUG')
SECRET_KEY = env('SECRET_KEY')
```

## 5. Production-Ready Implementation
Fail-fast on startup is crucial. If a required secret is missing, the application should crash immediately, not later during a user request.

```python
import environ
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    DATABASE_URL=(str, None)
)

# Only read .env locally. In production, rely on actual OS env vars.
if env('DJANGO_ENV', default='production') == 'development':
    environ.Env.read_env(BASE_DIR / '.env')

# Fail-fast validation
try:
    SECRET_KEY = env('SECRET_KEY')
except environ.ImproperlyConfigured as e:
    raise ImproperlyConfigured("SECRET_KEY is missing from environment") from e

DATABASES = {
    'default': env.db('DATABASE_URL')
}
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:**
```python
# settings.py
SECRET_KEY = os.environ.get('SECRET_KEY', 'default-insecure-key')
```
*Why it's bad:* If the environment variable fails to load in production, Django will silently fall back to the insecure default key, exposing the application to session hijacking.

## 7. Environment-Specific Behavior
| Variable | Local | Production |
|----------|-------|------------|
| `DATABASE_URL` | `sqlite:///db.sqlite3` | `postgres://user:pass@host/db` |
| `CACHE_URL` | `locmemcache://` | `redis://host:6379/0` |

## 8. Local Development Issues
🔴 SYMPTOM: `.env` file changes are not reflecting.
🔍 CAUSE: The Python process caches environment variables on startup.
🔧 FIX: Restart the Django development server manually, or ensure you aren't exporting conflicting variables in your shell profile.

## 9. Production Issues
🔴 INCIDENT: App bootlooping in Kubernetes.
- **Severity:** HIGH
- **Investigation:** Pods were crashing with `ImproperlyConfigured: Set the DATABASE_URL environment variable`.
- **Root Cause:** A typo in the Kubernetes ConfigMap (`DATBASE_URL`).
- **Fix:** Corrected the typo. The fail-fast design prevented the app from serving 500 errors to users, as the load balancer never marked the pod as ready.

## 10. Failure Simulation
Intentionally remove `DATABASE_URL` from your `.env` file and try to start `runserver`. It should throw an `ImproperlyConfigured` exception immediately.

## 11. Decision Matrix
| Tool | Pros | Cons |
|------|------|------|
| `os.environ` | Built-in | Manual type casting required |
| `django-environ` | 12-factor standard, URL parsing | Extra dependency |
| `python-decouple` | Simple, generic | Less Django-specific features |

## 12. Senior-Level Questions
**Q: How do you handle environment variables during CI (GitHub Actions)?**
A: You should provide dummy values for secrets in CI configurations or use a `.env.test` file. Never use production values in CI unless specifically deploying.

## 13. Production Checklist
- [ ] No `default` values provided for sensitive keys (`SECRET_KEY`, DB creds).
- [ ] `.env` is included in `.gitignore`.
- [ ] All boolean flags are properly cast (e.g., using `env.bool()`).
