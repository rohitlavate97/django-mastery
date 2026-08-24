# Production Readiness Gate: The 50-Point Checklist

## Mental Model
Releasing software without a checklist relies on memory, and human memory fails under pressure. This checklist acts as an engineering gate. If any item is unchecked, the deployment is blocked.

## Database & ORM
1. [ ] **No N+1 Queries:** `django-debug-toolbar` shows < 10 queries per view. Used `select_related` / `prefetch_related`.
2. [ ] **Indexes:** All fields used in `filter()`, `exclude()`, or `order_by()` have `db_index=True` or `Index()`.
3. [ ] **Migrations Safe:** No `RunPython` migrations that mutate millions of rows in a single transaction.
4. [ ] **Connection Pooling:** PgBouncer or Django's `CONN_MAX_AGE` is configured (>0).
5. [ ] **Timeout:** `STATEMENT_TIMEOUT` is set in PostgreSQL to prevent rogue queries from locking the DB.

## Security
6. [ ] **Secret Management:** No secrets hardcoded. `.env` or AWS Parameter Store/Vault is used.
7. [ ] **DEBUG = False:** Explicitly verified in the production environment variables.
8. [ ] **Allowed Hosts:** `ALLOWED_HOSTS` contains the exact production domains.
9. [ ] **CORS:** `CORS_ALLOWED_ORIGINS` is strictly defined (no `*`).
10. [ ] **Admin URL:** Admin URL is changed from `/admin/` to something obscure (e.g., `/portal-access-99/`).
11. [ ] **Password Hashing:** Argon2id is the default hasher in `PASSWORD_HASHERS`.
12. [ ] **Secure Cookies:** `SESSION_COOKIE_SECURE = True` and `CSRF_COOKIE_SECURE = True`.

## Background Processing (Celery)
13. [ ] **Idempotency:** Tasks can be run twice safely without duplicating data or charging users twice.
14. [ ] **Retries:** Network calls within tasks use `autoretry_for` with exponential backoff.
15. [ ] **Timeouts:** All external HTTP requests (`requests.get`) have a strict `timeout=(3.0, 10.0)`.
16. [ ] **Dead Letter Queue:** Failed tasks are routed to a failure queue or logged to Sentry.

## Application Architecture
17. [ ] **Fat Models / Thin Views:** Business logic is in services, model managers, or models, NOT in views/serializers.
18. [ ] **Pagination:** ALL list endpoints have pagination enforced.
19. [ ] **Rate Limiting:** DRF `AnonRateThrottle` and `UserRateThrottle` are active.
20. [ ] **Logging:** Structured JSON logging is used so it can be parsed by Datadog/ELK.

## Infrastructure & DevOps
21. [ ] **Health Checks:** `/health/` endpoint exists and checks DB/Redis connectivity.
22. [ ] **Static Files:** WhiteNoise is configured, or static files are served via CDN/S3.
23. [ ] **Gunicorn Config:** Worker count is `(2 x CPU) + 1`. Threads are configured if using I/O bound tasks.
24. [ ] **Docker:** Image runs as a non-root user. No bloated base images (use `-slim`).
25. [ ] **Rollback Plan:** Migrations are reviewed to ensure they are backward compatible for zero-downtime deploys.
