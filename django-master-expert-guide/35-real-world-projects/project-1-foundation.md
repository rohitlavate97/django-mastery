# Blueprint: Project 1 - Foundation (REST API + Auth + Postgres + Docker)

## Mental Model
This is the baseline structure for every production-grade Django API. It establishes the unshakeable foundation that prevents structural rewrites later. If this foundation is solid, scaling is just adding resources. If it's flawed, you'll be fighting your own codebase.

```text
[ Request ] -> [ Nginx/Traefik ] -> [ Gunicorn (WSGI) ] -> [ Django ] -> [ PostgreSQL ]
                                          |                    |
                                          |-> [ Docker ] <-[ GitHub Actions ]
```

## 1. Project Initialization & Structure

### The Right Way to Start
Never use the default `django-admin startproject`. The default structure couples configuration to the root directory and makes Dockerization messy.

```bash
# Proper initialization
mkdir foundation_project && cd foundation_project
python -m venv venv
source venv/bin/activate
pip install django djangorestframework psycopg2-binary django-environ
django-admin startproject config .  # The dot is crucial!
python manage.py startapp core
```

### Directory Structure
```text
.
├── config/                 # Project configuration
│   ├── settings/           # Split settings
│   │   ├── base.py
│   │   ├── local.py
│   │   └── production.py
│   ├── urls.py
│   └── wsgi.py
├── core/                   # Shared resources, Custom User Model
│   ├── models.py
│   └── views.py
├── users/                  # App specific logic
├── manage.py
├── requirements/
│   ├── base.txt
│   ├── local.txt
│   └── production.txt
├── Dockerfile
└── docker-compose.yml
```

## 2. The Custom User Model (Mandatory)

🔴 **NEVER skip this step.** Changing the User model mid-project in Django is extremely painful and often requires dropping the database.

```python
# core/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid

class User(AbstractUser):
    """
    Custom user model replacing the default Django user.
    Uses UUIDs for primary keys to prevent exposing total user count.
    Uses email as the primary login field instead of username.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField('email address', unique=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username'] # Required for superuser creation

    def __str__(self):
        return self.email
```

**Configuration Update:**
```python
# config/settings/base.py
AUTH_USER_MODEL = 'core.User'
```

## 3. Environment Variables (django-environ)

Secrets should NEVER be in source control.

```python
# config/settings/base.py
import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False)
)
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('DJANGO_SECRET_KEY')
DEBUG = env('DEBUG')
DATABASES = {
    'default': env.db('DATABASE_URL')
}
```

## 4. Dockerization (Production-Ready)

### The Dockerfile
```dockerfile
# Dockerfile
FROM python:3.12-slim-bookworm

# Prevent Python from writing .pyc files & buffering stdout
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Install system dependencies (required for psycopg2 and other native extensions)
RUN apt-get update \
  && apt-get install -y --no-install-recommends gcc libpq-dev \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

COPY requirements/base.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . /app/

# Add a non-root user for security
RUN adduser --disabled-password --no-create-home django
USER django

# Run via Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "config.wsgi:application"]
```

### Local Development (docker-compose.yml)
```yaml
version: '3.8'

services:
  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - db
    
  db:
    image: postgres:16
    volumes:
      - postgres_data:/var/lib/postgresql/data/
    environment:
      - POSTGRES_USER=django
      - POSTGRES_PASSWORD=django
      - POSTGRES_DB=foundation_db
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

## 5. CI/CD: GitHub Actions

Automate linting and testing on every PR.

```yaml
# .github/workflows/ci.yml
name: Django CI

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

jobs:
  build:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: django
          POSTGRES_PASSWORD: django
          POSTGRES_DB: test_db
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v3
    - name: Set up Python 3.12
      uses: actions/setup-python@v4
      with:
        python-version: "3.12"
        cache: 'pip'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements/local.txt
    - name: Run Tests
      env:
        DATABASE_URL: postgres://django:django@localhost:5432/test_db
        DJANGO_SETTINGS_MODULE: config.settings.local
        DJANGO_SECRET_KEY: test-key-not-secret
      run: |
        python manage.py test
```
