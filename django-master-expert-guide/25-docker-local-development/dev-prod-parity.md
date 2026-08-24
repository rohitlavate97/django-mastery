# Dev/Prod Parity (The 12-Factor App)

## 1. Mental Model
```text
[Local Dev]                 [Staging]                 [Production]
OS: Docker (Linux)          OS: Docker (Linux)        OS: Docker (Linux)
DB: Postgres 16             DB: Postgres 16 (RDS)     DB: Postgres 16 (RDS)
Cache: Redis 7              Cache: Redis 7 (ElastiCache) Cache: Redis 7 (ElastiCache)
Config: .env.local          Config: Vault/K8s Secs    Config: Vault/K8s Secs
```
Dev/Prod parity aims to keep development, staging, and production as similar as possible. Divergence in backing services, operating systems, or configuration mechanisms guarantees "it works on my machine" bugs.

## 2. Why It Exists
Historically, developers used SQLite locally and PostgreSQL in production, or ran Windows locally and Linux in production. This led to catastrophic deployments where code worked flawlessly in dev but crashed immediately in prod due to subtle SQL dialect differences or file path separator issues.

## 3. Internal Working
The 12-Factor methodology demands strict separation of config from code. Django's `settings.py` should NOT contain hardcoded API keys or environment-specific logic (e.g., `if ENVIRONMENT == 'prod':`). Instead, it should read from the environment (`os.environ`), which is populated by `.env` files locally or container orchestrators in production.

## 4. Basic Implementation
```python
# 🔴 ANTI-PATTERN: Environment branching in settings
# settings.py
import os

ENVIRONMENT = os.environ.get('ENV', 'dev')

if ENVIRONMENT == 'dev':
    DEBUG = True
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': 'db.sqlite3'}}
elif ENVIRONMENT == 'prod':
    DEBUG = False
    DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', ...}}
```
*Why it's bad:* Violates parity. You are testing against a fundamentally different database locally.

## 5. Production-Ready Implementation
Use `django-environ` to enforce a unified configuration interface.

```python
# ✅ PRODUCTION-READY
# settings.py
import environ
import os

env = environ.Env(
    # set casting, default value
    DEBUG=(bool, False)
)

# Set the project base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Only read .env locally (in prod, these come from the system environment)
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# unified configuration
DEBUG = env('DEBUG')
SECRET_KEY = env('SECRET_KEY')

# Reads DATABASE_URL=postgres://user:pass@host:port/db
DATABASES = {
    'default': env.db(),
}

# Reads CACHE_URL=redis://host:port/1
CACHES = {
    'default': env.cache(),
}

# Security
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])
```

## 6. Anti-Patterns
🔴 **Different Backing Services:** SQLite locally, Postgres in prod. Use Docker Compose to run Postgres locally!
🔴 **Different Code Versions:** Deploying "dirty" git states to production, or using fundamentally different build processes for staging vs prod.

## 7. Environment-Specific Behavior
| Environment | Configuration Source | Backing Services |
|-------------|----------------------|------------------|
| Local | `.env` file | Docker Compose containers |
| CI | GitHub Secrets | Ephemeral Service Containers |
| Production | K8s Secrets / AWS SSM | Managed Services (RDS, ElastiCache) |

## 8. Local Development Issues
🔴 **SYMPTOM:** Django throws `environ.exceptions.ImproperlyConfigured: Set the DATABASE_URL environment variable`.
🔍 **CAUSE:** The `.env` file is missing, or the developer forgot to define `DATABASE_URL`.
🔧 **FIX:** `django-environ` is doing its job by failing fast. Provide a `.env.example` template in the repository.

## 9. Production Issues
🔴 **INCIDENT:** Paginator was wildly inaccurate in production, but worked perfectly locally.
* **Severity:** Medium
* **Investigation:** The query used `.order_by('?')` to randomize results. SQLite processes this differently than PostgreSQL, and the dataset size in Prod was 1000x larger.
* **Root Cause:** A subtle deviation in database engine behavior combined with data volume disparity.
* **Fix:** Enforced PostgreSQL 16 via Docker Compose for all developers. Removed `.order_by('?')` due to inherent Postgres performance issues on large tables.

## 10. Failure Simulation
To see why SQLite != Postgres, write a Django query using `ArrayField` or `JSONField` specific lookups. It will crash locally if using SQLite, forcing you to adopt Dockerized Postgres.

## 11. Decision Matrix
| Config Strategy | Pros | Cons |
|-----------------|------|------|
| Split settings (`base.py`, `local.py`, `prod.py`) | Easy to comprehend initially | High drift risk, duplicated code |
| Single settings + `django-environ` | Strictly 12-factor, zero drift | Requires robust env var injection everywhere |

## 12. Senior-Level Questions
**Q: If dev and prod should be identical, how do you handle features that cost money per API call (like SMS or AI generation) during local development?**
A: Use mock backends or abstract adapters. For email, use Mailpit locally (traps emails). For SMS/AI, create a `ConsoleAdapter` that prints to the terminal locally, injected via an environment variable `SMS_BACKEND=console`. The *architecture* remains identical, only the target endpoint changes.

## 13. Production Checklist
- [ ] No `if ENV == 'prod':` logic exists in the codebase.
- [ ] `django-environ` or similar is used for ALL external configuration.
- [ ] Local database engine and version EXACTLY match production (via Docker).
- [ ] `DEBUG=False` is strictly enforced in Staging and Production via environment variables, with no hardcoded fallback to True.
