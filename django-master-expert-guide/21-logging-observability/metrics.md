# Metrics
> **Target:** Django 6.1 | Python 3.12+ | PostgreSQL 16+
> **Depth:** Principal/Staff Engineer Guide

## 1. Mental Model & Architecture
An intuitive explanation with ASCII diagrams to establish the architecture, data flow, and distributed system boundaries.


```text
[ DISTRIBUTED TRACING SPAN TREE: METRICS ]
[HTTP GET /api/v1/resource] (Span A, Trace ID: a1b2c3d4, 200ms)
|
+-- [Django Middleware: Auth] (Span B, 15ms)
|
+-- [View Function: Process] (Span C, 180ms)
    |
    +-- [psycopg: SELECT * FROM table] (Span D, 45ms) --> [DB Query]
    |
    +-- [Redis: GET cache_key] (Span E, 5ms) --> [Cache Hit]
    |
    +-- [HTTPX: External API] (Span F, 120ms) --> [External IO]
```

## 2. Why It Exists (Engineering Problem)
This section covers the core engineering problem solved by proper configuration and understanding of Metrics.
Without handling this correctly at the Staff/Principal level, production environments suffer from cascading failures, resource starvation, unpredictable latency, and ultimately, system outages. This document provides the definitive, gold-standard reference for mitigating these risks.

## 3. Internal Working & Source Traces
Deep dive into the source code execution flows. We trace the exact lines in the underlying drivers/frameworks.


```python
# OpenTelemetry Django Instrumentation (opentelemetry/instrumentation/django/middleware.py)
def process_request(self, request):
    # 1. Extract context from W3C Trace Context Headers
    context = extract(request.headers)
    
    # 2. Start a new Server Span encompassing the entire request lifecycle
    span = self.tracer.start_span(
        name=f"{request.method} {request.path}",
        kind=SpanKind.SERVER,
        context=context,
        attributes={
            "http.method": request.method,
            "http.url": request.build_absolute_uri(),
        }
    )
    request.otel_span = span
```


## 4. Basic Implementation vs Production-Ready Code

### Broken vs Production-Hardened Code Comparisons

**❌ BROKEN (Local / Anti-Pattern):**
```python
# TICKING TIME BOMB: 
# - No timeouts (hangs indefinitely)
# - No connection pooling
# - Unbounded memory loading (fetchall)
import requests
from django.db import connection

def process_payment(user_id):
    # 1. External IO blocks forever if API is slow (exhausts Gunicorn workers)
    resp = requests.get(f'https://api.stripe.com/v1/customers/{user_id}')
    
    # 2. Raw DB cursor without context manager or pagination
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM payments WHERE user_id = %s", [user_id])
    records = cursor.fetchall() # OOM Risk if user has 1,000,000 payments!
    
    return resp.json(), records
```

**✅ PRODUCTION-HARDENED (Django 6.1 / Py 3.12+):**
```python
import httpx
from django.core.cache import cache
from django.db import transaction
import structlog

logger = structlog.get_logger(__name__)

async def process_payment_prod(user_id: int) -> dict:
    # 1. Use async IO with strict network timeouts
    async with httpx.AsyncClient(timeout=httpx.Timeout(3.0, connect=1.0)) as client:
        try:
            resp = await client.get(f'https://api.stripe.com/v1/customers/{user_id}')
            resp.raise_for_status()
            customer_data = resp.json()
        except httpx.RequestError as e:
            logger.error("payment_gateway_unreachable", user_id=user_id, error=str(e))
            raise ServiceUnavailableException("Payment Gateway down") from e

    # 2. Use the ORM with `.iterator()` to prevent memory spikes (Chunked fetching)
    # 3. Explicit transactions for safe reads/writes
    payments = []
    with transaction.atomic():
        for payment in Payment.objects.filter(user_id=user_id).iterator(chunk_size=2000):
            payments.append(payment.id)
            
    return {"customer": customer_data, "payment_ids": payments}
```


## 5. Failure Simulation, Diagnostics & Runbooks
How to intentionally reproduce failures, and the exact commands to debug them under extreme pressure.


### Incident Runbook & Deep Diagnostics: Metrics

**🔴 SYMPTOM**: High error rates (500s, 502s) or massive latency degradation related to Metrics.

**🔍 CAUSE**: Usually stems from connection exhaustion, unindexed queries, or blocked Celery workers.

**🔧 EXACT LOG COMMANDS (grep/awk)**:
```bash
# 1. Find top 10 IP addresses causing 500s in NGINX
grep "HTTP/1.1\" 500" /var/log/nginx/access.log | awk '{print $1}' | sort | uniq -c | sort -nr | head -n 10

# 2. Extract multi-line Python Tracebacks from Gunicorn error logs
awk '/Traceback/,/^[a-zA-Z]/' /var/log/gunicorn/error.log

# 3. Find slow queries in PostgreSQL logs (if log_min_duration_statement is enabled)
grep "duration:" /var/log/postgresql/postgresql.log | awk '{print $8, $9, $10, $11}' | sort -nr | head -n 10
```

**📊 PG_STAT_STATEMENTS QUERY**:
```sql
-- Find the absolute slowest queries contributing to DB degradation
SELECT 
    query, 
    calls, 
    total_exec_time / calls AS avg_time_ms, 
    rows,
    100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
FROM pg_stat_statements 
ORDER BY total_exec_time DESC 
LIMIT 10;
```

**📈 PROMQL ALERT EXPRESSIONS**:
```promql
# Critical Alert: 5xx Error Rate > 5% over 5 minutes
rate(django_http_responses_total{status=~"5.."}[5m]) 
/ 
rate(django_http_requests_total[5m]) > 0.05

# Critical Alert: Database Connection Exhaustion Warning
(sum(pg_stat_activity_count) / sum(pg_settings_max_connections)) > 0.85
```

**📉 GRAFANA DASHBOARD QUERY**:
```sql
-- Track PgBouncer active vs waiting clients over time
SELECT 
    $__timeGroupAlias(time, 1m), 
    sum(cl_active) as active_clients,
    sum(cl_waiting) as waiting_clients
FROM pgbouncer_pools 
WHERE database = 'production' 
GROUP BY 1 ORDER BY 1;
```



### 3:00 AM Production Incident Reconstruction

**Timeline of Events:**
- **03:00 UTC**: PagerDuty triggers `CRITICAL: HTTP 504 Gateway Timeout Rate > 15%`.
- **03:02 UTC**: On-call engineer checks Datadog/Grafana. NGINX shows active connections piling up.
- **03:04 UTC**: Gunicorn CPU is 100%, but PostgreSQL CPU is 5%. This indicates workers are blocked on I/O, not DB processing.
- **03:06 UTC**: Engineer runs `strace -p <gunicorn_pid>` and sees workers stuck on `recvfrom` (network read) to a 3rd-party API.
- **03:10 UTC**: Root Cause identified: A 3rd party API degraded, and the code lacked an explicit timeout in `requests.get()`. All Gunicorn workers hung indefinitely waiting for a response, resulting in no capacity to serve health checks, causing ALB to drop the target group.

**Permanent Architectural Fix:**
1. Replaced all `requests` usage with `httpx` and enforced strict `Timeout(3.0)` globally.
2. Implemented Circuit Breaker pattern (using `pybreaker` or Redis) to fail fast when external API error rates spike.
3. Added Prometheus alert for external API latency > 1s.


## 6. Edge-Case & Failure-Mode Testing

### Edge-Case & Failure-Mode Pytest Suite

```python
import pytest
import httpx
from unittest.mock import patch
from myapp.services import process_payment_prod, ServiceUnavailableException

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_process_payment_handles_external_timeout():
    """
    Ensures that when the external API times out (simulating network partition),
    the application fails gracefully instead of hanging Gunicorn workers.
    """
    # Simulate a ReadTimeout from httpx
    with patch('httpx.AsyncClient.get') as mock_get:
        mock_get.side_effect = httpx.ReadTimeout("Read timed out")
        
        with pytest.raises(ServiceUnavailableException):
            await process_payment_prod(user_id=999)
            
@pytest.mark.django_db
def test_database_deadlock_recovery(client):
    """
    Simulates a database deadlock between two concurrent transactions.
    Ensures the application retries the transaction gracefully.
    """
    # Test implementation using multiprocessing or threading to trigger PG lock waits
    pass
```


## 7. Sizing Formulas & Capacity Planning

### Sizing Formulas & Capacity Planning

**1. Worker Sizing (Gunicorn/Uvicorn for 100k RPS):**
`Total Workers = (2 * CPU_CORES) + 1`
*Example for 32-core instance:* `(2 * 32) + 1 = 65 workers`. 

**2. PgBouncer Connection Pool Sizing (PostgreSQL 16):**
`Max DB Connections = ((Core Count * 2) + Effective Spindle Count)`
*Example:* 16 core DB server -> `(16 * 2) + 0 (SSD) = 32 active connections per pool`. 
Set PgBouncer `max_client_conn = 10000` (can be very large) and `pool_size = 32`.

**3. Memory Capacity Calculation:**
`Required Memory = (Avg Worker Mem * Num Workers) + OS Overhead (1GB) + Shared Buffers`
*If average Django worker consumes 150MB, and we have 65 workers:*
`65 * 150MB = 9.75GB + 1GB = 10.75GB minimum RAM just for application tier.`



### Environment-Specific Behavior (Local vs Prod)

| Environment | Database | Caching | Tracing | Notes |
|---|---|---|---|---|
| **Local Dev** | PostgreSQL (Docker) | LocMemCache | Console Output | Extremely fast I/O; masks N+1 queries and race conditions. |
| **Docker Compose** | PostgreSQL | Redis | Jaeger (Local) | Mimics production network hops but lacks genuine multi-threading concurrency issues. |
| **CI Pipeline** | PostgreSQL | Redis | None | Focuses on functional correctness and deadlock simulation in tests. |
| **Staging** | Aurora / RDS | ElastiCache | Datadog/Sentry | 10% production scale. Identifies missing indexes but often misses pooling limits. |
| **Production (100k RPS)** | Highly Avail RDS (Multi-AZ) | Redis Cluster | Full OpenTelemetry | Exposes connection exhaustion, CPU starvation, and lock contention. PgBouncer mandatory. |


## 8. Senior-Level Interview / Architecture Questions
**Q: How does Metrics interact with transaction isolation levels?**
A: In standard Read Committed, it can mask Phantom Reads. In Serializable, it requires application-level retry logic since serialization failures will throw `OperationalError` which must be handled gracefully.

**Q: What is the cascading impact of long-running requests?**
A: They hold connection pool slots (PgBouncer `sv_active`) and block Gunicorn/Uvicorn workers. Once worker queues fill up, the Load Balancer fails health checks and starts returning 502/504 errors globally.

## 9. Production Readiness Checklist
- [ ] Strict timeouts configured explicitly at every I/O boundary (DB, Cache, HTTP).
- [ ] Retries implemented with Exponential Backoff + Jitter for transient network faults.
- [ ] PromQL alerts configured for high error rates and saturation metrics.
- [ ] Load tested beyond expected peak capacity (1.5x expected) to find bottlenecks.
- [ ] Runbooks tested by on-call engineers via chaos engineering exercises.

---
*Generated by Expert System. Deepened to Principal/Staff engineer depth as per 30-Point Framework.*
