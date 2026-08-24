# Django Mastery: New Project Checklist

This checklist ensures a Django project starts with a production-ready foundation. Missing these steps early causes technical debt that is exceptionally painful to fix later (e.g., swapping the User model after initial migrations).

## 1. Project Structure & Initialization

- [ ] **Python Version**: Enforce Python 3.12+ in `pyproject.toml` or `Pipfile`.
- [ ] **Dependency Management**: Use a modern resolver (Poetry, uv, or pip-tools) instead of plain `requirements.txt`.
- [ ] **Project Layout**: Follow a standard layout (not default `django-admin startproject`):
  ```text
  repo_root/
  ├── config/             # Project settings (was project_name/)
  │   ├── settings/
  │   │   ├── base.py
  │   │   ├── local.py
  │   │   ├── test.py
  │   │   └── production.py
  │   ├── urls.py
  │   ├── wsgi.py
  │   └── asgi.py
  ├── core/               # Shared utilities, mixins, custom User model
  ├── apps/               # Domain-specific Django apps
  ├── manage.py
  ├── pyproject.toml
  └── docker-compose.yml
  ```
- [ ] **Git Ignore**: Apply a comprehensive Python/Django `.gitignore`.

## 2. The Custom User Model (CRITICAL)

**Rule: NEVER run `python manage.py migrate` before doing this.**

- [ ] **Create `core` app**: `python manage.py startapp core`.
- [ ] **Define `User` model**: Inherit from `AbstractUser` (or `AbstractBaseUser` for strict setups).
  ```python
  from django.contrib.auth.models import AbstractUser
  class User(AbstractUser):
      pass
  ```
- [ ] **Register Model**: In `config/settings/base.py`, add `AUTH_USER_MODEL = 'core.User'`.
- [ ] **Update Admin**: Register the custom User model in `core/admin.py`.

## 3. Settings Management

- [ ] **Environment Variables**: Use `django-environ` or `python-decouple` for 12-factor compliance.
- [ ] **Settings Split**: Create `base.py`, `local.py`, and `production.py`.
- [ ] **SECRET_KEY**: Remove default key from settings. Load strictly from `os.environ`.
- [ ] **DEBUG**: Ensure `DEBUG = False` by default, override only in `local.py`.
- [ ] **Database URL**: Configure `DATABASES` using `env.db()` (URL format).

## 4. Code Quality & Pre-Commit

- [ ] **Linter & Formatter**: Configure `ruff` (replaces flake8, isort, black).
- [ ] **Pre-commit Hooks**: Install `pre-commit` and configure `.pre-commit-config.yaml`.
- [ ] **Type Checking**: Setup `mypy` and `django-stubs`.
- [ ] **EditorConfig**: Add `.editorconfig` for consistent spacing across IDEs.

## 5. Containerization (Docker)

- [ ] **Dockerfile**: Create a multi-stage Dockerfile for production.
- [ ] **Non-Root User**: Ensure the Docker container runs the app as a non-root user.
- [ ] **Docker Compose**: Setup `docker-compose.yml` with:
  - Django web service
  - PostgreSQL 16+
  - Redis (for cache and Celery)
  - Celery worker (optional initially, but recommended)

## 6. Testing Foundation

- [ ] **Pytest Setup**: Install `pytest` and `pytest-django`.
- [ ] **Test Config**: Add `pytest.ini`.
- [ ] **Factory Setup**: Install `factory_boy` for test data generation.
- [ ] **Coverage**: Install `pytest-cov` and aim for >80% initial coverage.

## 7. PostgreSQL Configuration

- [ ] **Psycopg3**: Install `psycopg[binary]` (v3), not `psycopg2`.
- [ ] **Connection Pooling**: Configure `CONN_MAX_AGE` (e.g., 60 seconds) in database settings.
- [ ] **Timezones**: Set `USE_TZ = True` and use aware datetimes everywhere.
