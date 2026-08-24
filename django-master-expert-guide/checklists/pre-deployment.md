# Django Mastery: Pre-Deployment Checklist

Execute this checklist before any major release or when setting up a new environment.

## 1. Django Framework Checks

- [ ] **Deployment Check**: Run `python manage.py check --deploy` and resolve all warnings.
- [ ] **DEBUG Mode**: Verify `DEBUG = False` in production environment.
- [ ] **SECRET_KEY**: Ensure the secret key is cryptographically secure, >50 chars, and rotated if exposed.
- [ ] **ALLOWED_HOSTS**: Explicitly list all production domains (e.g., `['www.example.com', 'example.com']`). No `*`.

## 2. Security & Headers

- [ ] **SECURE_SSL_REDIRECT**: Set to `True`.
- [ ] **SECURE_HSTS_SECONDS**: Set to `31536000` (1 year).
- [ ] **SECURE_HSTS_PRELOAD**: Set to `True`.
- [ ] **SECURE_HSTS_INCLUDE_SUBDOMAINS**: Set to `True`.
- [ ] **SESSION_COOKIE_SECURE**: Set to `True`.
- [ ] **CSRF_COOKIE_SECURE**: Set to `True`.
- [ ] **SECURE_BROWSER_XSS_FILTER**: Set to `True` (Django < 3.0) or rely on CSP.
- [ ] **SECURE_CONTENT_TYPE_NOSNIFF**: Set to `True`.
- [ ] **Admin URL**: Change from `^admin/` to a custom/obscured path (e.g., `^hq-admin/`).

## 3. Database & Caching (PostgreSQL & Redis)

- [ ] **Connection Pooling**: Ensure PgBouncer or similar is running and Django's `CONN_MAX_AGE` is tuned (e.g., `60`).
- [ ] **Cache Backend**: Configure Redis using `django-redis`. Ensure `CACHES` is defined correctly.
- [ ] **Session Engine**: Store sessions in cache or cached_db to reduce DB load (`SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'`).
- [ ] **Migrations**: Run `python manage.py makemigrations --check --dry-run` in CI to ensure no missing migrations.

## 4. Static & Media Files

- [ ] **Static Root**: `STATIC_ROOT` is defined and points to an absolute path.
- [ ] **WhiteNoise / CDN**: Configure WhiteNoise for static file serving, or sync to S3/CDN.
- [ ] **Manifest Storage**: Use `ManifestStaticFilesStorage` to generate unique file names (cache busting).
- [ ] **Media Files**: Ensure user uploads (media) are stored externally (e.g., AWS S3 via `django-storages`), not on the local container.

## 5. Error Reporting & Logging

- [ ] **Sentry/APM**: Integrate Sentry (`sentry-sdk`) or DataDog.
- [ ] **Logging Config**: Define a clear `LOGGING` dictionary. Log WARNING and ERROR to console (stdout/stderr) for Docker log ingestion.
- [ ] **Admin Emails**: Configure `ADMINS` and email backend for critical fallback alerts if APM fails.

## 6. Performance & WSGI/ASGI

- [ ] **Gunicorn/Uvicorn**: Use a production-grade WSGI/ASGI server.
- [ ] **Worker Tuning**: Set Gunicorn workers to `(2 x $num_cores) + 1`.
- [ ] **Timeouts**: Configure Gunicorn timeout (e.g., 30s) to kill hung workers.
- [ ] **Max Requests**: Set `--max-requests` and `--max-requests-jitter` to prevent memory leaks over time.
