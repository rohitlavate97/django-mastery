# 12-Factor App Methodology in Django

## 1. Mental Model
```text
The 12-Factor App is a manifesto for building scalable SaaS applications.
It ensures that your Django app can run anywhere (Local, CI, Kubernetes, Heroku) 
without code changes, scales horizontally, and deploys cleanly.
```

## 2. Why It Exists
Historically, apps relied heavily on the server they ran on (local config files, local storage, sticky sessions). When cloud computing arrived, these apps couldn't scale horizontally. The 12-factor methodology enforces architectural rules that make apps cloud-native.

## 3. Internal Working
Mapping the 12 factors to Django specifically:

1. **Codebase:** One Git repository, multiple deployments (Dev, Staging, Prod).
2. **Dependencies:** Explicitly declare everything in `requirements.txt` or `Pipfile`. No implicit system packages.
3. **Config:** Store config in the environment (`django-environ`).
4. **Backing Services:** Treat databases (PostgreSQL), caches (Redis), and email (SMTP) as attached resources. Connect via URL.
5. **Build, Release, Run:** Separate the build stage (Docker build) from the release stage (running migrations) and run stage (Gunicorn).
6. **Processes:** Execute the app as one or more stateless processes. Store state in the database, not memory.
7. **Port Binding:** Export services via port binding (Django/Gunicorn listens on a port, Nginx reverse-proxies to it).
8. **Concurrency:** Scale out via the process model (add more Gunicorn workers, add Celery workers).
9. **Disposability:** Maximize robustness with fast startup and graceful shutdown (handle `SIGTERM` cleanly).
10. **Dev/Prod Parity:** Keep local, staging, and production as similar as possible (use Docker, Postgres everywhere).
11. **Logs:** Treat logs as event streams (log to `stdout`, let Docker/fluentd handle routing).
12. **Admin Processes:** Run admin/management tasks (migrations) as one-off processes in an identical environment.

## 4. Basic Implementation (Factor III: Config)
Using environment variables instead of hardcoded configs.
```python
# settings.py
import environ
env = environ.Env()
DATABASES = {'default': env.db('DATABASE_URL')}
```

## 5. Production-Ready Implementation (Factor XI: Logs)
Django's default logging often writes to files, which violates the "treat logs as event streams" rule. In production, log to `stdout` in JSON format.

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(levelname)s %(asctime)s %(module)s %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
            # Factor 11: Write to stdout/stderr
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb (Factor VI Violation):**
```python
# views.py
GLOBAL_USER_CACHE = {}

def get_user(request, user_id):
    if user_id not in GLOBAL_USER_CACHE:
        GLOBAL_USER_CACHE[user_id] = User.objects.get(id=user_id)
    return GLOBAL_USER_CACHE[user_id]
```
*Why it's bad:* Django workers are stateless. `GLOBAL_USER_CACHE` only exists in the memory of ONE Gunicorn worker. Subsequent requests might hit a different worker and get a cache miss, or worse, stale data. Always use an attached backing service (Redis) for state.

## 7. Environment-Specific Behavior
| Factor | Local | Production |
|--------|-------|------------|
| X: Dev/Prod Parity | SQLite | PostgreSQL |
*Note:* The table above highlights a common violation. To truly follow 12-factor, you should use PostgreSQL locally via Docker to maintain parity.

## 8. Local Development Issues
🔴 SYMPTOM: Code works locally on SQLite but fails on Staging with PostgreSQL.
🔍 CAUSE: SQLite doesn't enforce strict typing on `CharField` lengths, or you used a Postgres-specific feature like `ArrayField`.
🔧 FIX: Enforce Dev/Prod Parity (Factor X). Run Postgres locally using `docker-compose`.

## 9. Production Issues
🔴 INCIDENT: Data Loss on Pod Restart
- **Severity:** HIGH
- **Investigation:** User uploads (images) were returning 404s after a Kubernetes deployment.
- **Root Cause:** Media files were being saved to local disk (violating Factor VI: Stateless Processes). When the pod restarted, the ephemeral disk was wiped.
- **Fix:** Treat file storage as a backing service (Factor IV). Configure `django-storages` with AWS S3 for media files.

## 10. Failure Simulation
Deploy a Django app that writes a file to local disk, then run two instances of it behind a load balancer. Upload a file. Refresh the page repeatedly. You will get intermittent 404s depending on which instance serves the request. This proves the necessity of statelessness.

## 11. Decision Matrix
| Practice | 12-Factor Way | Legacy Way |
|----------|---------------|------------|
| Background Jobs | Celery (separate stateless process) | Threading inside Django |
| Migrations | `manage.py migrate` in a release phase script | Running migration on app startup |
| Secret Management | Environment Variables | `config.ini` outside source control |

## 12. Senior-Level Questions
**Q: How does Django's `runserver` violate disposability (Factor IX)?**
A: `runserver` does not handle `SIGTERM` gracefully. In production, Gunicorn handles signals properly, finishing active requests before shutting down, ensuring no user gets a connection drop mid-request.

## 13. Production Checklist
- [ ] Config is 100% in environment variables.
- [ ] Logs go to `stdout`/`stderr`.
- [ ] No state (files, sessions, caches) is stored on local disk or worker memory.
- [ ] Dev, Staging, and Prod use the exact same backing services (e.g., Postgres, not SQLite).
