# Project 2: Scalable Application

## Architecture
- Django 6.1
- PostgreSQL 16
- Redis 7 (Caching & Celery Broker)
- Celery (Async Tasks)
- Prometheus (Metrics)

## Setup

1. Copy `.env.example` to `.env`
2. Build & run Docker containers:
   ```bash
   docker-compose up --build
   ```

## Running Tests
```bash
docker-compose exec web pytest
```

## Running Load Tests
```bash
docker-compose exec web locust -f locustfile.py
```

## Prometheus
Available at `http://localhost:9090`
