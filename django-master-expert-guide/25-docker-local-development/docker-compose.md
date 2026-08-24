# Docker Compose for Local Development

## 1. Mental Model
```text
[Browser] -> [localhost:8000 (Django)]
                    |
          +---------+---------+
          |                   |
    [PostgreSQL:5432]   [Redis:6379]
                              |
                     [Celery Worker/Beat]
```
`docker-compose.yml` is the orchestrator for your local development symphony. It defines the relationships, networks, and persistent storage required to boot an entire micro-ecosystem that mimics production.

## 2. Why It Exists
Running PostgreSQL, Redis, Celery, and Django locally requires setting up complex configurations and ensuring version parity. `docker-compose` allows you to spin up the entire stack with `docker-compose up`, guaranteeing that every developer runs the exact same versions of infrastructure services.

## 3. Internal Working
Docker Compose reads the YAML specification and translates it into API calls to the Docker daemon. It creates an isolated bridge network by default, allowing services to resolve each other by their service names (e.g., `redis://redis:6379/0`).

## 4. Basic Implementation
```yaml
# 🔴 ANTI-PATTERN: Brittle Compose File
version: '3'
services:
  web:
    build: .
    ports:
      - "8000:8000"
  db:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: pass
```
*Why it's bad:* No volume mounts (data lost on restart), no health checks (Django will crash if it boots before Postgres is ready), no env files.

## 5. Production-Ready Implementation (Local Dev)
```yaml
# ✅ ROBUST LOCAL DEVELOPMENT
version: '3.9'

x-app-defaults: &app-defaults
  build:
    context: .
    dockerfile: Dockerfile
  volumes:
    - .:/app  # Live reload
  env_file:
    - .env.local
  depends_on:
    db:
      condition: service_healthy
    redis:
      condition: service_healthy

services:
  django:
    <<: *app-defaults
    command: python manage.py runserver 0.0.0.0:8000
    ports:
      - "8000:8000"

  celery_worker:
    <<: *app-defaults
    command: celery -A core worker -l info

  celery_beat:
    <<: *app-defaults
    command: celery -A core beat -l info

  db:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    env_file:
      - .env.local
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres}"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
      
  mailpit:
    image: axllent/mailpit
    ports:
      - "8025:8025" # Web UI
      - "1025:1025" # SMTP

volumes:
  postgres_data:
```

## 6. Anti-Patterns
🔴 **Missing Healthchecks:** Relying on `depends_on` without `condition: service_healthy`. Docker only waits for the *container* to start, not for the database inside it to accept connections.
🔴 **Hardcoded Secrets:** Committing `POSTGRES_PASSWORD` into the YAML. Use `.env` files.
🔴 **Host Port Conflicts:** Not exposing mapping ports, or exposing them and conflicting with local databases (e.g., running local Postgres AND docker Postgres).

## 7. Environment-Specific Behavior
| Feature | Local Compose | Production Compose / K8s |
|---------|---------------|--------------------------|
| Volumes | Bind mounts `.:/app` for live reload | Named volumes or external storage |
| Command | `manage.py runserver` | `gunicorn` |
| Overrides| `docker-compose.override.yml` is auto-loaded | Strict, CI-driven YAML |

## 8. Local Development Issues
🔴 **SYMPTOM:** Django container crashes with `django.db.utils.OperationalError: could not connect to server: Connection refused`.
🔍 **CAUSE:** Django started executing before Postgres finished initializing its data directory.
🔧 **FIX:** Add `healthcheck` to the Postgres service and `depends_on: db: condition: service_healthy` to the Django service.

## 9. Production Issues (Compose in Prod)
🔴 **INCIDENT:** Database data wiped during deployment.
* **Severity:** Critical (Data Loss)
* **Investigation:** The operator ran `docker-compose down -v` instead of `docker-compose down`.
* **Root Cause:** Using Docker Compose for production stateful services without external backups and accidentally triggering volume deletion.
* **Fix:** Move database to managed RDS/Cloud SQL. If using Compose, never run `down -v`.

## 10. Failure Simulation
Modify the Postgres healthcheck command to an invalid command `["CMD-SHELL", "false"]`. Observe how Docker Compose blocks the Django container from ever starting.

## 11. Decision Matrix
| Tool | Local Dev | Prod Single Node | Prod Multi-Node |
|------|-----------|------------------|-----------------|
| Docker Compose | Standard Choice | Acceptable | Anti-pattern |
| Kubernetes / Helm | Too complex | Overkill | Standard Choice |

## 12. Senior-Level Questions
**Q: How do you handle database migrations in a docker-compose setup reliably?**
A: Do not run migrations via the `command` override in the web service (e.g., `command: bash -c "python manage.py migrate && python manage.py runserver"`). This can lead to race conditions if multiple containers try to migrate simultaneously. Instead, run them explicitly `docker-compose exec web python manage.py migrate`, or use an `init` container pattern that runs migrations before the web service boots.

## 13. Production Checklist (Local Dev)
- [ ] YAML Anchors (`<<: *app-defaults`) used for DRY configuration.
- [ ] Healthchecks configured for ALL backing services.
- [ ] Persistent named volumes defined for databases.
- [ ] Mail catcher (Mailpit/Mailhog) included for local email testing.
- [ ] Bind mounts configured for instant code reload.
