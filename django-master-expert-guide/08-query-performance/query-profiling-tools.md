# Django Mastery: Query Profiling Tools

You cannot improve what you do not measure. This file covers the trinity of query profiling across different environments.

---

## 1. Local Development: `django-debug-toolbar`

The standard for local query visibility.

**Setup:**
```python
# settings.py
if DEBUG:
    INSTALLED_APPS += [\'debug_toolbar\']
    MIDDLEWARE = [\'debug_toolbar.middleware.DebugToolbarMiddleware\'] + MIDDLEWARE
    INTERNAL_IPS = [\'127.0.0.1\']
```

**What it gives you:**
- Total query count and time.
- EXPLAIN analysis directly in the browser UI.
- Stack traces for exactly which Python line triggered the query.

**Anti-Pattern:** Leaving it active in production (huge security and performance risk).

---

## 2. Staging / Heavy Testing: `django-silk`

`django-debug-toolbar` injects HTML. It breaks JSON API endpoints. `django-silk` intercepts requests and logs profiling data to the database, offering a separate dashboard.

**Use Case:** Profiling DRF API endpoints on a staging server.

**Setup:**
```python
# settings.py
INSTALLED_APPS += [\'silk\']
MIDDLEWARE = [\'silk.middleware.SilkyMiddleware\'] + MIDDLEWARE

SILKY_PYTHON_PROFILER = True
SILKY_PYTHON_PROFILER_BINARY = True # Uses cProfile
```

**Warning:** Silk adds significant overhead. Do not run it constantly in production. Use it on staging or turn it on dynamically for a few minutes in production if absolutely necessary.

---

## 3. Production Continuous Profiling: `pg_stat_statements`

The holy grail of production database profiling. It runs inside PostgreSQL and aggregates query statistics continuously with near-zero overhead.

### Setup in PostgreSQL
1. Add to `postgresql.conf`:
   ```ini
   shared_preload_libraries = \'pg_stat_statements\'
   ```
2. Restart PostgreSQL.
3. Run SQL: `CREATE EXTENSION pg_stat_statements;`

### Crucial Queries for DevOps/Backend Engineers

**1. Find Top 5 Most Time-Consuming Queries (Overall System Impact)**
```sql
SELECT query, 
       calls, 
       total_plan_time + total_exec_time AS total_time,
       mean_exec_time as mean_time, 
       rows
FROM pg_stat_statements
ORDER BY total_plan_time + total_exec_time DESC
LIMIT 5;
```

**2. Find Highest Latency Queries (Slowest individual queries)**
```sql
SELECT query, mean_exec_time, max_exec_time 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 5;
```

**3. Find Memory/Disk Thrashing Queries (Missing Indexes)**
Look for high `shared_blks_read` (disk read) vs `shared_blks_hit` (memory cache hit).
```sql
SELECT query, 
       shared_blks_hit, 
       shared_blks_read, 
       (shared_blks_hit::float / (shared_blks_hit + shared_blks_read + 1)) * 100 as hit_ratio
FROM pg_stat_statements 
WHERE shared_blks_read > 0
ORDER BY shared_blks_read DESC 
LIMIT 5;
```

---

## 4. APM Integration (Datadog / New Relic)

In modern microservices, use an APM tracer (e.g., `ddtrace` for Datadog).

```python
# Datadog injection wraps psycopg2
import ddtrace.auto
```

APMs inject a `sql.query` span into every HTTP request trace. This allows you to:
1. See the exact N+1 waterfall visually in Datadog.
2. Alert on "P99 Database Latency > 100ms".

---

## 5. Performance Regression Testing in CI

Use `pytest-django` to ensure performance doesn\'t degrade.

```python
import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_dashboard_query_limits(client, django_assert_max_num_queries):
    # Setup test data (100 users, etc)
    setup_complex_state()
    
    # Assert that this page NEVER exceeds 5 queries, even if data grows
    with django_assert_max_num_queries(5):
        response = client.get(reverse(\'dashboard\'))
        
    assert response.status_code == 200
```

## 6. Production Checklist
- [ ] `pg_stat_statements` is enabled on production PostgreSQL.
- [ ] APM is configured to capture database spans.
- [ ] Critical API endpoints have `django_assert_max_num_queries` tests in CI.
- [ ] Query plans for endpoints with >1M rows have been verified via `EXPLAIN`.
