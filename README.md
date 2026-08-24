# Django Mastery 🚀

> **A Principal-Level System for Mastering Django 6.1, Python 3.12+, and PostgreSQL 16+**

Welcome to **Django Mastery** — a comprehensive knowledge base, reference architecture, and hands-on curriculum designed to take you from a standard Django user to a senior/principal backend engineer who understands internals, diagnoses 2 AM production failures, designs high-concurrency systems, and leads architectural decisions.

---

## 📚 Knowledge Base Structure

The full master guide is organized into 38 deeply structured sections in [`django-master-expert-guide/`](django-master-expert-guide/README.md):

```text
django-master-expert-guide/
├── 00-learning-system/                # Mental models, Feynman method, practice routines
├── 01-python-foundations/             # Descriptors, metaclasses, concurrency, memory model
├── 02-web-http-networking/            # HTTP/2/3, TCP sockets, TLS, DNS, web security
├── 03-django-fundamentals/            # Project layout, settings architecture, admin security
├── 04-django-internals/               # AppRegistry, request lifecycle, descriptors, signals
├── 05-urls-views-middleware/          # URL resolver, FBV vs CBV, onion middleware, error handling
├── 06-templates-forms/                # Engine compilation, validation pipeline, HTMX vs SPA
├── 07-models-orm/                     # QuerySet compiler, advanced queries, fetch modes (6.1)
├── 08-query-performance/              # N+1 prevention, EXPLAIN ANALYZE, memory efficiency
├── 09-migrations-schema-evolution/    # Zero-downtime DDL, expand/contract, lock timeouts
├── 10-transactions-concurrency/       # ACID, isolation levels, select_for_update, deadlocks
├── 11-django-rest-framework/          # Serializers lifecycle, cursor pagination, rate limits
├── 12-authentication-authorization/   # Custom user model, Argon2, JWT rotation, RBAC/ABAC
├── 13-security/                       # OWASP Top 10, CSRF/CORS, SSRF, secret management
├── 14-settings-environments/          # Split settings, 12-Factor, zero-downtime secret rotation
├── 15-caching-redis/                  # Cache-aside, stampede locks, Redis Sentinel/Cluster
├── 16-background-jobs/                # Celery topology, idempotent tasks, dead letter queues
├── 17-async-asgi/                     # WSGI vs ASGI, sync_to_async boundary, event loops
├── 18-websockets-realtime/            # Django Channels, WebSocket scaling, Redis layers
├── 19-testing/                        # Pytest, factory_boy, concurrency tests, flaky test fixes
├── 20-debugging/                      # 12-step framework, 20+ operational incident runbooks
├── 21-logging-observability/          # JSON structured logging, OpenTelemetry, Prometheus metrics
├── 22-performance-load-testing/       # py-spy profiling, Locust load testing, capacity planning
├── 23-postgresql-production/          # Index deep dive, query plans, PgBouncer, autovacuum tuning
├── 24-external-integrations/          # Circuit breakers, httpx pooling, idempotent webhooks
├── 25-docker-local-development/       # Multi-stage Dockerfile, docker-compose, live debugpy
├── 26-ci-cd/                          # GitHub Actions pipelines, migration linters, zero-downtime
├── 27-production-deployment/          # Gunicorn/Uvicorn tuning, Nginx proxy, health checks
├── 28-cloud-architecture/             # AWS (ECS/RDS), GCP (Cloud Run/Cloud SQL), cost right-sizing
├── 29-kubernetes-scaling/             # K8s manifests, HPA, KEDA queue autoscaling
├── 30-production-incidents/           # Chaos engineering game days, blameless post-mortems
├── 31-issue-encyclopedia/             # 8 categories of production incident forensics
├── 32-architecture-patterns/          # Service layer, DDD, Event Outbox, multi-tenancy
├── 33-system-design/                  # Bitly, notifications, high-concurrency flash sales
├── 34-code-review/                    # Staff review checklist, subtle production bug teardowns
├── 35-real-world-projects/            # 3 progressive enterprise project blueprints
├── 36-senior-principal-knowledge/     # Engineering judgment, ADRs/RFCs, mentoring
├── 37-interview-scenarios/            # 30+ deep-dive questions, triage roleplays
├── checklists/                        # Pre-deployment, security, API & migration checklists
├── troubleshooting/                   # Fast lookup matrix & common error traces
└── glossary/                          # 100+ production backend terms defined
```

---

## 🛠️ Reference Implementations (`projects/`)

Executable, containerized, test-backed reference codebases:

1. **[Project 1 — Production Foundation](projects/project-1-foundation/)**
   - Custom UUIDv7/Email User Model, JWT Authentication, DRF API with Strict Serializer Validation, Multi-Stage Docker, Pytest Concurrency Tests, CI Matrix.
2. **[Project 2 — Scalable Backend](projects/project-2-scalable/)**
   - Redis Caching Layer, Celery Task Queues, Ingest-First Webhook Handlers, Circuit Breakers, Prometheus Metrics, Locust Performance Suite.
3. **[Project 3 — Enterprise Multi-Tenant SaaS](projects/project-3-enterprise/)**
   - PostgreSQL Row/Schema Isolation, Real-Time WebSockets (Channels), Distributed Lock Reservation, Outbox Pattern, K8s Manifests.

---

## 🧪 Hands-on Practice Suite (`exercises/`)

Interactive, test-driven coding challenges with automated Pytest grading:

- **[01 Descriptors](exercises/01_descriptors/)**: Implement custom model field encryption descriptors (`__get__`, `__set__`).
- **[02 ORM Optimization](exercises/02_orm_optimization/)**: Eliminate 50+ N+1 queries with strict `django_assert_num_queries(2)` limits.
- **[03 Concurrency & Race Conditions](exercises/03_concurrency_race/)**: Fix multi-threaded balance deduction race conditions using `select_for_update()`.
- **[04 Redis Rate Limiter](exercises/04_redis_rate_limiter/)**: Write atomic sliding window rate limiter Lua scripts in Redis.
- **[05 Circuit Breaker](exercises/05_circuit_breaker/)**: Build a stateful Circuit Breaker (`CLOSED`, `OPEN`, `HALF_OPEN`) with fallback routing.
- **[06 Transactional Outbox](exercises/06_outbox_pattern/)**: Reliable event publishing without two-phase commit.
- **[07 Tenant Data Isolation](exercises/07_tenant_isolation/)**: Single-database multi-tenant scoping via ContextVars and custom Managers.
- **[08 Safe Migration Operations](exercises/08_custom_migration_operation/)**: Zero-downtime PostgreSQL concurrent index migrations with lock timeouts.
- **[09 Signal Transaction Timing](exercises/09_signals_transaction_timing/)**: Celery task dispatching safely using `transaction.on_commit()`.
- **[10 HMAC Request Signing](exercises/10_hmac_auth_backend/)**: API-to-API SHA-256 HMAC authentication with anti-replay verification.

```bash
# Run all exercises
pytest exercises/

# Run a specific exercise
pytest exercises/01_descriptors/
```

---

## 📊 Runnable Benchmarks (`benchmarks/`)

```bash
# Run synthetic ORM, pagination, and concurrency performance benchmarks
python3 benchmarks/benchmark_suite.py
```

---

## 📑 Production Cheat Sheets (`cheatsheets/`)

- **[ORM & QuerySet Syntax](cheatsheets/orm-lookup-cheatsheet.md)**: Lookups, `Q()`, `F()`, `Subquery()`, `Window()`, Django 6.1 `FETCH_RAISE`.
- **[PostgreSQL 16+ Tuning](cheatsheets/postgresql-tuning-cheatsheet.md)**: Hardware formulas, autovacuum config, lock diagnostics.
- **[Gunicorn & Nginx](cheatsheets/gunicorn-nginx-cheatsheet.md)**: Worker sizing, keepalive buffers, reverse proxy headers.
- **[Celery Production](cheatsheets/celery-production-cheatsheet.md)**: Worker flags, retry policies, transaction safety.

---

## 💻 Interactive CLI Companion (`cli/`)

```bash
# Search the entire 38-section knowledge base offline
python3 cli/main.py search "select_for_update"

# View any production readiness checklist instantly
python3 cli/main.py checklist pre-deployment

# Review spaced repetition active-recall flashcards
python3 cli/main.py flashcards

# Simulate a live 2 AM production outage triage
python3 cli/main.py incident

# Run automated tests for an exercise
python3 cli/main.py exercise 1

# Take the interactive Staff-level self-assessment quiz
python3 cli/main.py assess
```

---

## ⚡ The 30-Point Framework

Every concept and architectural design follows the **30-Point Framework**:
- **UNDERSTAND:** Mental models, internal source tracing, trade-off matrix
- **BUILD:** Basic minimal vs. production-hardened implementations
- **BREAK:** Environment-by-environment failure simulations (Local, Docker, CI, Staging, 100k RPS Production)
- **DEBUG & FIX:** 12-step systematic diagnostics, SQL inspection, safe mitigation
- **PREVENT & EVOLVE:** Architectural patterns, alerts, preventive regression tests

---

## 🚀 Quick Navigation

- 📖 **Start Learning:** [00-learning-system/methodology.md](django-master-expert-guide/00-learning-system/methodology.md)
- ⚙️ **Internals Trace:** [04-django-internals/request-response-lifecycle.md](django-master-expert-guide/04-django-internals/request-response-lifecycle.md)
- 🗄️ **PostgreSQL Query Plans:** [23-postgresql-production/query-plans.md](django-master-expert-guide/23-postgresql-production/query-plans.md)
- 🚨 **Incident Runbooks:** [20-debugging/runbooks/500-errors.md](django-master-expert-guide/20-debugging/runbooks/500-errors.md)
- ✅ **Pre-Deployment Checklist:** [checklists/pre-deployment.md](django-master-expert-guide/checklists/pre-deployment.md)
