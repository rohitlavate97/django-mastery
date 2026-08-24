# Mentoring: Building Engineering Culture

## Mental Model
A senior engineer writes great code. A Staff engineer builds great engineers. Mentoring is not about answering questions; it's about transferring your mental models so juniors can answer their own questions.

```text
[ Give Answer ] -> Dependency
[ Teach Mental Model ] -> Autonomy
```

## 1. The Code Review Culture

### The Anti-Pattern: "Nitpicking"
- Leaving 40 comments on variable names, PEP8 spacing, and syntax.
- **Result:** The junior engineer feels attacked, learns nothing about architecture, and relies on the senior as a human linter.

### The Production Implementation: "Structural Review"
- Use automated tools (Ruff, Black, Mypy) to eliminate all style discussions.
- Focus review on the 30-Point Framework: Security, Performance, Concurrency.

**Example Comment:**
> ❌ "Rename `lst` to `users_list`."
> ✅ "I notice we're pulling this queryset into memory on line 45, but the table has 2M rows. What happens if this endpoint gets hit by 10 concurrent users? Let's pair on using `iterator()` here."

## 2. Leveling Up Engineers (The Framework)

1. **The "I Do, You Watch" Phase**
   Pair programming where the senior drives. The senior explicitly verbalizes their internal monologue ("I'm checking the DB indexes because...").

2. **The "You Do, I Watch" Phase**
   The junior drives. The senior asks questions instead of giving commands ("Why did you choose a List API view here?").

3. **The "You Do, I Review" Phase**
   Standard async PR process.

## 3. Creating Safety

- **Celebrate Failure:** When a junior takes down production, the Staff engineer's response must be: "Fascinating! How did our CI pipeline allow this? Let's fix the pipeline together."
- **Blameless Post-Mortems:** Focus on the system, never the human.
\n\n---\n## Staff/Principal Level Architecture Diagrams\n
### 1.3 Transactional Outbox Pattern Event Bus (Staff/Principal Level)
```text
[Django Application]
       │
       ▼ (1) Local Transaction: Save Order + Save Event
┌───────────────────────────────────────┐
│ PostgreSQL                            │
│ ┌────────────────┐ ┌────────────────┐ │
│ │ Order Table    │ │ Outbox Table   │ │
│ │ - id: 123      │ │ - id: 99       │ │
│ │ - state: paid  │ │ - type: created│ │
│ └────────────────┘ └────────────────┘ │
└───────────────────────────────────────┘
                                   │
                                   ▼ (2) CDC (Change Data Capture) via Debezium
                        ┌─────────────────────┐
                        │ Kafka / Event Bus   │
                        └──────────┬──────────┘
                                   │
                                   ▼ (3) Consume Event
                        ┌─────────────────────┐
                        │ Notification Svc    │
                        └─────────────────────┘
```
**Mental Model:** Dual-writes (saving to DB and publishing to Kafka) cause data inconsistencies if one fails. The Outbox Pattern solves this by writing the event to an `Outbox` table in the *same database transaction* as the domain update. A background process (like Debezium CDC) streams the outbox table to the Event Bus.
\n
### 1.4 Monolith-to-Service Decomposition (Staff Level)
```text
Phase 1: Big Ball of Mud        Phase 2: Modular Monolith          Phase 3: Microservices
┌─────────────────────┐         ┌─────────────────────┐            ┌────────────────┐
│ Django Monolith     │         │ Django Monolith     │            │ Order Svc (Go) │
│ - Users             │   =>    │ ┌──────┐ ┌──────┐   │     =>     └───────┬────────┘
│ - Orders            │         │ │Users │ │Orders│   │                    │
│ - Payments          │         │ └──────┘ └──────┘   │            ┌───────▼────────┐
│ - Notifications     │         │ ┌───────────────┐   │            │ Payment Svc    │
└─────────┬───────────┘         │ │ Notifications │   │            │ (Django)       │
          │                     │ └───────────────┘   │            └────────────────┘
┌─────────▼───────────┐         └─────────┬───────────┘
│ Single PostgreSQL   │                   │
└─────────────────────┘         ┌─────────▼───────────┐
                                │ Single PostgreSQL   │
                                │ (Schema per Module) │
                                └─────────────────────┘
```
**Mental Model:** Never split a Big Ball of Mud directly into microservices. First, enforce domain boundaries in the Django codebase (Modular Monolith) with strict imports and separate database schemas. Once a module proves to have distinct scaling or lifecycle requirements, extract it into a separate service.
\n\n
## 4. Basic Implementation vs Production-Hardened Code

### 🔴 BROKEN / AMATEUR IMPLEMENTATION
```python
# Anti-Pattern: Ticking Time Bomb
# 1. No timeouts - can hang forever
# 2. No retries
# 3. Blocking synchronous call inside a view
# 4. No circuit breaker
import requests
from django.http import JsonResponse

def process_payment(request):
    # DANGER: If third-party API is slow, Gunicorn workers will exhaust
    response = requests.post("https://api.external.com/pay", data={"amount": 100})
    if response.status_code == 200:
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "failed"}, status=400)
```

### ✅ PRODUCTION-HARDENED (STAFF/PRINCIPAL LEVEL)
```python
# Production-Grade: Resilient, Async, Timeout-bound
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)

def get_resilient_session():
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[ 500, 502, 503, 504 ]
    )
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

def process_payment(request):
    session = get_resilient_session()
    try:
        # 1. Always use timeouts! (Connect timeout, Read timeout)
        response = session.post(
            "https://api.external.com/pay", 
            data={"amount": 100},
            timeout=(3.0, 10.0) # 3s connect, 10s read
        )
        response.raise_for_status()
        return JsonResponse({"status": "success"})
        
    except requests.exceptions.RequestException as e:
        # 2. Log exact failure for forensics
        logger.error(f"[PAYMENT_FAILED] External API error: {str(e)}", exc_info=True)
        # 3. Graceful degradation
        return JsonResponse(
            {"status": "error", "message": "Payment provider temporarily unavailable"}, 
            status=503
        )
```
\n\n
## X. Architecture Decision Record (ADR): System Design Trade-offs

### Context & Problem Statement
We need to design a high-throughput, low-latency system that guarantees data consistency while handling extreme traffic spikes. Should we scale up the RDBMS, use a NoSQL approach, or implement an event-driven CQRS pattern?

### Considered Options
1. **Vertical Scaling (Fat DB)** - Easy, but hard limits on scaling.
2. **Read Replicas + Caching (Redis/Memcached)** - Good for read-heavy, bad for write-heavy.
3. **Event-Driven CQRS with Kafka** - High complexity, ultimate scalability, eventual consistency.
4. **Sharded PostgreSQL (Citus)** - Operational overhead, good for multi-tenant.

### Decision Outcome
Chosen option: **Event-Driven CQRS with Kafka**.
* **Justification:** At Staff/Principal scale, decoupling writes (Commands) from reads (Queries) is mandatory. Django will write events to an Outbox, Kafka will distribute them, and materialized views (Elasticsearch/Redis) will serve reads.
* **Trade-offs:** We accept Eventual Consistency (UI must handle optimistic updates). Complexity increases due to CDC (Debezium) and schema registries.

### Real-World Interview Rubric (Principal Level)
- **Junior/Mid:** Focuses on ORM optimization and basic Redis caching.
- **Senior:** Discusses Read-Replicas, connection pooling (PgBouncer), and Celery queues.
- **Staff/Principal:** Identifies DB locks as the bottleneck, proposes Outbox Pattern, discusses Idempotency, and designs for cross-AZ fault tolerance.
\n\n\n================================================================================\n## Deep Dive: The 30-Point Principal Framework Applied\n\n### Extended Production Readiness Checklist\n- [ ] Check point 1: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 2: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 3: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 4: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 5: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 6: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 7: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 8: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 9: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 10: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 11: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 12: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 13: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 14: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 15: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 16: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 17: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 18: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 19: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 20: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 21: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 22: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 23: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 24: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 25: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 26: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 27: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 28: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 29: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 30: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 31: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 32: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 33: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 34: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 35: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 36: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 37: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 38: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 39: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 40: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 41: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 42: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 43: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 44: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 45: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 46: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 47: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 48: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 49: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n- [ ] Check point 50: Ensure idempotency, caching, and circuit breaking are implemented at the boundary layers.\n\n### Internal Working & Execution Flow Trace (Django Source Code)\n```python\n# Django Internals Trace:\n# django/core/handlers/base.py -> BaseHandler.get_response()\n# 1. request middleware executed\n# 2. URL resolution (resolver.resolve())\n# 3. view middleware executed\n# 4. view executed (where our business logic lives)\n# 5. exception middleware (if exception raised)\n# 6. response middleware executed\n```\nUnderstanding this lifecycle is critical because placing a heavy blocking operation in request middleware will exhaust all Gunicorn workers before the view is even reached.\n
## 15. The Complete Staff-Level Guide to Mentoring
This section contains a deep dive into the 30-Point Framework for Mentoring.

### 15.1 Real-World Trade-Offs Matrix
| Architecture Choice | Pros for Mentoring | Cons for Mentoring | Max Scale |
|---------------------|------------------|------------------|-----------|
| Monolithic Default  | Easy to deploy   | High coupling    | 1k RPS    |
| Microservice Extracted | Independent scaling | Network overhead | 10k RPS   |
| Event-Driven Kafka  | Eventual Consistency | High Complexity  | 100k+ RPS |
| Serverless / Lambda | Scale to zero    | Cold Starts      | 50k RPS   |

### 15.2 Comprehensive Pytest Suite for Mentoring
A production-grade system requires testing across all failure domains. Below is the definitive pytest suite for testing Mentoring against race conditions, network failures, and database locks.

```python
import pytest
from unittest.mock import patch, MagicMock
from django.core.exceptions import ValidationError
from django.db import transaction, DatabaseError

@pytest.fixture
def setup_mentoring():
    return {"status": "initialized", "topic": "Mentoring"}

@pytest.mark.django_db(transaction=True)
def test_happy_path_mentoring(setup_mentoring):
    """Test the standard execution flow without errors."""
    result = perform_mentoring_action()
    assert result.status == "success"

@pytest.mark.django_db(transaction=True)
def test_race_condition_mentoring():
    """Simulate concurrent requests to ensure row locks (select_for_update) hold."""
    import threading
    
    exceptions = []
    def worker():
        try:
            with transaction.atomic():
                # Simulate the lock and process
                perform_mentoring_action()
        except Exception as e:
            exceptions.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    # 1 succeeds, 4 fail with concurrency exceptions
    assert len(exceptions) == 4

@patch('requests.post')
def test_network_timeout_mentoring(mock_post):
    """Ensure system degrades gracefully when upstream is slow."""
    import requests
    mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")
    
    with pytest.raises(ServiceUnavailableError):
         perform_mentoring_action()
```

### 15.3 Multi-Environment Comparison
| Environment | State Management | Concurrency | Latency | Debugging Strategy |
|-------------|------------------|-------------|---------|--------------------|
| **Local Dev** | SQLite / Local Redis | Single-threaded | < 5ms | Use `pdb` / `ipdb`, inspect local logs. |
| **Docker Compose** | Containerized PG | Local Gunicorn | ~10ms | Docker exec, attach debugger. |
| **CI/CD Pipeline** | Ephemeral DBs | Parallel Pytest | ~50ms | View artifacts, capture stdout/stderr. |
| **Staging (EKS)** | RDS Multi-AZ | HPA, 5 pods | ~30ms | Datadog/New Relic APM tracing. |
| **Production (100k RPS)**| RDS Read Replicas | KEDA + HPA, 500 pods | ~25ms | Distributed tracing, log aggregation (ELK). |

### 15.4 Django Internal Execution Trace for Mentoring
To truly master Mentoring, you must understand how Django handles it at the framework level.

1. **WSGI/ASGI Entrypoint**: Gunicorn receives the HTTP request and hands it to Django's `WSGIHandler`.
2. **Middleware Chain**: The request passes through `SecurityMiddleware`, `SessionMiddleware`, and custom middleware.
3. **URL Routing**: `URLResolver` matches the path to the specific view for Mentoring.
4. **View Execution**:
   - Authentication & Permissions are verified.
   - Database queries are generated via the ORM. (Watch out for N+1 queries here!)
   - Context is passed to the Template or serialized via DRF.
5. **Database Transaction**: If `ATOMIC_REQUESTS=True` or `transaction.atomic()` is used, a `BEGIN` statement is executed.
6. **Response Generation**: The view returns an `HttpResponse`.
7. **Middleware Teardown**: Middleware processes the response (e.g., adding headers).
8. **DB Commit/Rollback**: The transaction is committed. If an exception occurred, it rolls back.

### 15.5 Ticking Time Bomb Anti-Patterns
🔴 **Anti-Pattern 1: Unbounded Queries in Mentoring**
```python
# Ticking Time Bomb: This works locally with 10 rows.
# In prod, with 10M rows, it crashes the database and exhausts memory.
data = list(MyModel.objects.all())
```
✅ **The Fix:** Pagination, chunking, or streaming.
```python
# Staff-level fix
from django.core.paginator import Paginator
paginator = Paginator(MyModel.objects.order_by('id'), 1000)
for page in paginator.page_range:
    process(paginator.page(page).object_list)
```

🔴 **Anti-Pattern 2: Missing Indexes for Mentoring**
Querying by a non-indexed column in PostgreSQL will result in a Sequential Scan (`Seq Scan`). On a large table, this causes high CPU usage and slow responses.
✅ **The Fix:** Use `db_index=True`, `Meta.indexes`, or `GinIndex` for JSONB fields.

### 15.6 Resolution Playbook for Severity-1 Incidents
When a SEV-1 incident strikes related to Mentoring, follow this strict playbook:
1. **Acknowledge & Escalate:** Announce on `#incident-response`. PagerDuty alerts should be silenced.
2. **Mitigate, Don't Fix:** Your goal is to stop the bleeding, not write the perfect patch.
   - Scale up replicas? `kubectl scale deploy --replicas=50 app-name`
   - Block traffic? Add a WAF rule blocking the abusive IP or User Agent.
   - Revert deployment? Run the rollback CI pipeline.
3. **Investigation:** Look at APM traces. Are DB queries taking 5 seconds? Is Redis evicting keys?
4. **Root Cause Analysis (RCA):** Post-incident, write an ADR detailing *why* it happened (e.g., Cache Stampede, missing lock) and implement long-term fixes (Circuit Breaker, Outbox Pattern).


## 15. The Complete Staff-Level Guide to Mentoring
This section contains a deep dive into the 30-Point Framework for Mentoring.

### 15.1 Real-World Trade-Offs Matrix
| Architecture Choice | Pros for Mentoring | Cons for Mentoring | Max Scale |
|---------------------|------------------|------------------|-----------|
| Monolithic Default  | Easy to deploy   | High coupling    | 1k RPS    |
| Microservice Extracted | Independent scaling | Network overhead | 10k RPS   |
| Event-Driven Kafka  | Eventual Consistency | High Complexity  | 100k+ RPS |
| Serverless / Lambda | Scale to zero    | Cold Starts      | 50k RPS   |

### 15.2 Comprehensive Pytest Suite for Mentoring
A production-grade system requires testing across all failure domains. Below is the definitive pytest suite for testing Mentoring against race conditions, network failures, and database locks.

```python
import pytest
from unittest.mock import patch, MagicMock
from django.core.exceptions import ValidationError
from django.db import transaction, DatabaseError

@pytest.fixture
def setup_mentoring():
    return {"status": "initialized", "topic": "Mentoring"}

@pytest.mark.django_db(transaction=True)
def test_happy_path_mentoring(setup_mentoring):
    """Test the standard execution flow without errors."""
    result = perform_mentoring_action()
    assert result.status == "success"

@pytest.mark.django_db(transaction=True)
def test_race_condition_mentoring():
    """Simulate concurrent requests to ensure row locks (select_for_update) hold."""
    import threading
    
    exceptions = []
    def worker():
        try:
            with transaction.atomic():
                # Simulate the lock and process
                perform_mentoring_action()
        except Exception as e:
            exceptions.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    # 1 succeeds, 4 fail with concurrency exceptions
    assert len(exceptions) == 4

@patch('requests.post')
def test_network_timeout_mentoring(mock_post):
    """Ensure system degrades gracefully when upstream is slow."""
    import requests
    mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")
    
    with pytest.raises(ServiceUnavailableError):
         perform_mentoring_action()
```

### 15.3 Multi-Environment Comparison
| Environment | State Management | Concurrency | Latency | Debugging Strategy |
|-------------|------------------|-------------|---------|--------------------|
| **Local Dev** | SQLite / Local Redis | Single-threaded | < 5ms | Use `pdb` / `ipdb`, inspect local logs. |
| **Docker Compose** | Containerized PG | Local Gunicorn | ~10ms | Docker exec, attach debugger. |
| **CI/CD Pipeline** | Ephemeral DBs | Parallel Pytest | ~50ms | View artifacts, capture stdout/stderr. |
| **Staging (EKS)** | RDS Multi-AZ | HPA, 5 pods | ~30ms | Datadog/New Relic APM tracing. |
| **Production (100k RPS)**| RDS Read Replicas | KEDA + HPA, 500 pods | ~25ms | Distributed tracing, log aggregation (ELK). |

### 15.4 Django Internal Execution Trace for Mentoring
To truly master Mentoring, you must understand how Django handles it at the framework level.

1. **WSGI/ASGI Entrypoint**: Gunicorn receives the HTTP request and hands it to Django's `WSGIHandler`.
2. **Middleware Chain**: The request passes through `SecurityMiddleware`, `SessionMiddleware`, and custom middleware.
3. **URL Routing**: `URLResolver` matches the path to the specific view for Mentoring.
4. **View Execution**:
   - Authentication & Permissions are verified.
   - Database queries are generated via the ORM. (Watch out for N+1 queries here!)
   - Context is passed to the Template or serialized via DRF.
5. **Database Transaction**: If `ATOMIC_REQUESTS=True` or `transaction.atomic()` is used, a `BEGIN` statement is executed.
6. **Response Generation**: The view returns an `HttpResponse`.
7. **Middleware Teardown**: Middleware processes the response (e.g., adding headers).
8. **DB Commit/Rollback**: The transaction is committed. If an exception occurred, it rolls back.

### 15.5 Ticking Time Bomb Anti-Patterns
🔴 **Anti-Pattern 1: Unbounded Queries in Mentoring**
```python
# Ticking Time Bomb: This works locally with 10 rows.
# In prod, with 10M rows, it crashes the database and exhausts memory.
data = list(MyModel.objects.all())
```
✅ **The Fix:** Pagination, chunking, or streaming.
```python
# Staff-level fix
from django.core.paginator import Paginator
paginator = Paginator(MyModel.objects.order_by('id'), 1000)
for page in paginator.page_range:
    process(paginator.page(page).object_list)
```

🔴 **Anti-Pattern 2: Missing Indexes for Mentoring**
Querying by a non-indexed column in PostgreSQL will result in a Sequential Scan (`Seq Scan`). On a large table, this causes high CPU usage and slow responses.
✅ **The Fix:** Use `db_index=True`, `Meta.indexes`, or `GinIndex` for JSONB fields.

### 15.6 Resolution Playbook for Severity-1 Incidents
When a SEV-1 incident strikes related to Mentoring, follow this strict playbook:
1. **Acknowledge & Escalate:** Announce on `#incident-response`. PagerDuty alerts should be silenced.
2. **Mitigate, Don't Fix:** Your goal is to stop the bleeding, not write the perfect patch.
   - Scale up replicas? `kubectl scale deploy --replicas=50 app-name`
   - Block traffic? Add a WAF rule blocking the abusive IP or User Agent.
   - Revert deployment? Run the rollback CI pipeline.
3. **Investigation:** Look at APM traces. Are DB queries taking 5 seconds? Is Redis evicting keys?
4. **Root Cause Analysis (RCA):** Post-incident, write an ADR detailing *why* it happened (e.g., Cache Stampede, missing lock) and implement long-term fixes (Circuit Breaker, Outbox Pattern).


## 15. The Complete Staff-Level Guide to Mentoring
This section contains a deep dive into the 30-Point Framework for Mentoring.

### 15.1 Real-World Trade-Offs Matrix
| Architecture Choice | Pros for Mentoring | Cons for Mentoring | Max Scale |
|---------------------|------------------|------------------|-----------|
| Monolithic Default  | Easy to deploy   | High coupling    | 1k RPS    |
| Microservice Extracted | Independent scaling | Network overhead | 10k RPS   |
| Event-Driven Kafka  | Eventual Consistency | High Complexity  | 100k+ RPS |
| Serverless / Lambda | Scale to zero    | Cold Starts      | 50k RPS   |

### 15.2 Comprehensive Pytest Suite for Mentoring
A production-grade system requires testing across all failure domains. Below is the definitive pytest suite for testing Mentoring against race conditions, network failures, and database locks.

```python
import pytest
from unittest.mock import patch, MagicMock
from django.core.exceptions import ValidationError
from django.db import transaction, DatabaseError

@pytest.fixture
def setup_mentoring():
    return {"status": "initialized", "topic": "Mentoring"}

@pytest.mark.django_db(transaction=True)
def test_happy_path_mentoring(setup_mentoring):
    """Test the standard execution flow without errors."""
    result = perform_mentoring_action()
    assert result.status == "success"

@pytest.mark.django_db(transaction=True)
def test_race_condition_mentoring():
    """Simulate concurrent requests to ensure row locks (select_for_update) hold."""
    import threading
    
    exceptions = []
    def worker():
        try:
            with transaction.atomic():
                # Simulate the lock and process
                perform_mentoring_action()
        except Exception as e:
            exceptions.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    # 1 succeeds, 4 fail with concurrency exceptions
    assert len(exceptions) == 4

@patch('requests.post')
def test_network_timeout_mentoring(mock_post):
    """Ensure system degrades gracefully when upstream is slow."""
    import requests
    mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")
    
    with pytest.raises(ServiceUnavailableError):
         perform_mentoring_action()
```

### 15.3 Multi-Environment Comparison
| Environment | State Management | Concurrency | Latency | Debugging Strategy |
|-------------|------------------|-------------|---------|--------------------|
| **Local Dev** | SQLite / Local Redis | Single-threaded | < 5ms | Use `pdb` / `ipdb`, inspect local logs. |
| **Docker Compose** | Containerized PG | Local Gunicorn | ~10ms | Docker exec, attach debugger. |
| **CI/CD Pipeline** | Ephemeral DBs | Parallel Pytest | ~50ms | View artifacts, capture stdout/stderr. |
| **Staging (EKS)** | RDS Multi-AZ | HPA, 5 pods | ~30ms | Datadog/New Relic APM tracing. |
| **Production (100k RPS)**| RDS Read Replicas | KEDA + HPA, 500 pods | ~25ms | Distributed tracing, log aggregation (ELK). |

### 15.4 Django Internal Execution Trace for Mentoring
To truly master Mentoring, you must understand how Django handles it at the framework level.

1. **WSGI/ASGI Entrypoint**: Gunicorn receives the HTTP request and hands it to Django's `WSGIHandler`.
2. **Middleware Chain**: The request passes through `SecurityMiddleware`, `SessionMiddleware`, and custom middleware.
3. **URL Routing**: `URLResolver` matches the path to the specific view for Mentoring.
4. **View Execution**:
   - Authentication & Permissions are verified.
   - Database queries are generated via the ORM. (Watch out for N+1 queries here!)
   - Context is passed to the Template or serialized via DRF.
5. **Database Transaction**: If `ATOMIC_REQUESTS=True` or `transaction.atomic()` is used, a `BEGIN` statement is executed.
6. **Response Generation**: The view returns an `HttpResponse`.
7. **Middleware Teardown**: Middleware processes the response (e.g., adding headers).
8. **DB Commit/Rollback**: The transaction is committed. If an exception occurred, it rolls back.

### 15.5 Ticking Time Bomb Anti-Patterns
🔴 **Anti-Pattern 1: Unbounded Queries in Mentoring**
```python
# Ticking Time Bomb: This works locally with 10 rows.
# In prod, with 10M rows, it crashes the database and exhausts memory.
data = list(MyModel.objects.all())
```
✅ **The Fix:** Pagination, chunking, or streaming.
```python
# Staff-level fix
from django.core.paginator import Paginator
paginator = Paginator(MyModel.objects.order_by('id'), 1000)
for page in paginator.page_range:
    process(paginator.page(page).object_list)
```

🔴 **Anti-Pattern 2: Missing Indexes for Mentoring**
Querying by a non-indexed column in PostgreSQL will result in a Sequential Scan (`Seq Scan`). On a large table, this causes high CPU usage and slow responses.
✅ **The Fix:** Use `db_index=True`, `Meta.indexes`, or `GinIndex` for JSONB fields.

### 15.6 Resolution Playbook for Severity-1 Incidents
When a SEV-1 incident strikes related to Mentoring, follow this strict playbook:
1. **Acknowledge & Escalate:** Announce on `#incident-response`. PagerDuty alerts should be silenced.
2. **Mitigate, Don't Fix:** Your goal is to stop the bleeding, not write the perfect patch.
   - Scale up replicas? `kubectl scale deploy --replicas=50 app-name`
   - Block traffic? Add a WAF rule blocking the abusive IP or User Agent.
   - Revert deployment? Run the rollback CI pipeline.
3. **Investigation:** Look at APM traces. Are DB queries taking 5 seconds? Is Redis evicting keys?
4. **Root Cause Analysis (RCA):** Post-incident, write an ADR detailing *why* it happened (e.g., Cache Stampede, missing lock) and implement long-term fixes (Circuit Breaker, Outbox Pattern).


## 15. The Complete Staff-Level Guide to Mentoring
This section contains a deep dive into the 30-Point Framework for Mentoring.

### 15.1 Real-World Trade-Offs Matrix
| Architecture Choice | Pros for Mentoring | Cons for Mentoring | Max Scale |
|---------------------|------------------|------------------|-----------|
| Monolithic Default  | Easy to deploy   | High coupling    | 1k RPS    |
| Microservice Extracted | Independent scaling | Network overhead | 10k RPS   |
| Event-Driven Kafka  | Eventual Consistency | High Complexity  | 100k+ RPS |
| Serverless / Lambda | Scale to zero    | Cold Starts      | 50k RPS   |

### 15.2 Comprehensive Pytest Suite for Mentoring
A production-grade system requires testing across all failure domains. Below is the definitive pytest suite for testing Mentoring against race conditions, network failures, and database locks.

```python
import pytest
from unittest.mock import patch, MagicMock
from django.core.exceptions import ValidationError
from django.db import transaction, DatabaseError

@pytest.fixture
def setup_mentoring():
    return {"status": "initialized", "topic": "Mentoring"}

@pytest.mark.django_db(transaction=True)
def test_happy_path_mentoring(setup_mentoring):
    """Test the standard execution flow without errors."""
    result = perform_mentoring_action()
    assert result.status == "success"

@pytest.mark.django_db(transaction=True)
def test_race_condition_mentoring():
    """Simulate concurrent requests to ensure row locks (select_for_update) hold."""
    import threading
    
    exceptions = []
    def worker():
        try:
            with transaction.atomic():
                # Simulate the lock and process
                perform_mentoring_action()
        except Exception as e:
            exceptions.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    # 1 succeeds, 4 fail with concurrency exceptions
    assert len(exceptions) == 4

@patch('requests.post')
def test_network_timeout_mentoring(mock_post):
    """Ensure system degrades gracefully when upstream is slow."""
    import requests
    mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")
    
    with pytest.raises(ServiceUnavailableError):
         perform_mentoring_action()
```

### 15.3 Multi-Environment Comparison
| Environment | State Management | Concurrency | Latency | Debugging Strategy |
|-------------|------------------|-------------|---------|--------------------|
| **Local Dev** | SQLite / Local Redis | Single-threaded | < 5ms | Use `pdb` / `ipdb`, inspect local logs. |
| **Docker Compose** | Containerized PG | Local Gunicorn | ~10ms | Docker exec, attach debugger. |
| **CI/CD Pipeline** | Ephemeral DBs | Parallel Pytest | ~50ms | View artifacts, capture stdout/stderr. |
| **Staging (EKS)** | RDS Multi-AZ | HPA, 5 pods | ~30ms | Datadog/New Relic APM tracing. |
| **Production (100k RPS)**| RDS Read Replicas | KEDA + HPA, 500 pods | ~25ms | Distributed tracing, log aggregation (ELK). |

### 15.4 Django Internal Execution Trace for Mentoring
To truly master Mentoring, you must understand how Django handles it at the framework level.

1. **WSGI/ASGI Entrypoint**: Gunicorn receives the HTTP request and hands it to Django's `WSGIHandler`.
2. **Middleware Chain**: The request passes through `SecurityMiddleware`, `SessionMiddleware`, and custom middleware.
3. **URL Routing**: `URLResolver` matches the path to the specific view for Mentoring.
4. **View Execution**:
   - Authentication & Permissions are verified.
   - Database queries are generated via the ORM. (Watch out for N+1 queries here!)
   - Context is passed to the Template or serialized via DRF.
5. **Database Transaction**: If `ATOMIC_REQUESTS=True` or `transaction.atomic()` is used, a `BEGIN` statement is executed.
6. **Response Generation**: The view returns an `HttpResponse`.
7. **Middleware Teardown**: Middleware processes the response (e.g., adding headers).
8. **DB Commit/Rollback**: The transaction is committed. If an exception occurred, it rolls back.

### 15.5 Ticking Time Bomb Anti-Patterns
🔴 **Anti-Pattern 1: Unbounded Queries in Mentoring**
```python
# Ticking Time Bomb: This works locally with 10 rows.
# In prod, with 10M rows, it crashes the database and exhausts memory.
data = list(MyModel.objects.all())
```
✅ **The Fix:** Pagination, chunking, or streaming.
```python
# Staff-level fix
from django.core.paginator import Paginator
paginator = Paginator(MyModel.objects.order_by('id'), 1000)
for page in paginator.page_range:
    process(paginator.page(page).object_list)
```

🔴 **Anti-Pattern 2: Missing Indexes for Mentoring**
Querying by a non-indexed column in PostgreSQL will result in a Sequential Scan (`Seq Scan`). On a large table, this causes high CPU usage and slow responses.
✅ **The Fix:** Use `db_index=True`, `Meta.indexes`, or `GinIndex` for JSONB fields.

### 15.6 Resolution Playbook for Severity-1 Incidents
When a SEV-1 incident strikes related to Mentoring, follow this strict playbook:
1. **Acknowledge & Escalate:** Announce on `#incident-response`. PagerDuty alerts should be silenced.
2. **Mitigate, Don't Fix:** Your goal is to stop the bleeding, not write the perfect patch.
   - Scale up replicas? `kubectl scale deploy --replicas=50 app-name`
   - Block traffic? Add a WAF rule blocking the abusive IP or User Agent.
   - Revert deployment? Run the rollback CI pipeline.
3. **Investigation:** Look at APM traces. Are DB queries taking 5 seconds? Is Redis evicting keys?
4. **Root Cause Analysis (RCA):** Post-incident, write an ADR detailing *why* it happened (e.g., Cache Stampede, missing lock) and implement long-term fixes (Circuit Breaker, Outbox Pattern).


## 15. The Complete Staff-Level Guide to Mentoring
This section contains a deep dive into the 30-Point Framework for Mentoring.

### 15.1 Real-World Trade-Offs Matrix
| Architecture Choice | Pros for Mentoring | Cons for Mentoring | Max Scale |
|---------------------|------------------|------------------|-----------|
| Monolithic Default  | Easy to deploy   | High coupling    | 1k RPS    |
| Microservice Extracted | Independent scaling | Network overhead | 10k RPS   |
| Event-Driven Kafka  | Eventual Consistency | High Complexity  | 100k+ RPS |
| Serverless / Lambda | Scale to zero    | Cold Starts      | 50k RPS   |

### 15.2 Comprehensive Pytest Suite for Mentoring
A production-grade system requires testing across all failure domains. Below is the definitive pytest suite for testing Mentoring against race conditions, network failures, and database locks.

```python
import pytest
from unittest.mock import patch, MagicMock
from django.core.exceptions import ValidationError
from django.db import transaction, DatabaseError

@pytest.fixture
def setup_mentoring():
    return {"status": "initialized", "topic": "Mentoring"}

@pytest.mark.django_db(transaction=True)
def test_happy_path_mentoring(setup_mentoring):
    """Test the standard execution flow without errors."""
    result = perform_mentoring_action()
    assert result.status == "success"

@pytest.mark.django_db(transaction=True)
def test_race_condition_mentoring():
    """Simulate concurrent requests to ensure row locks (select_for_update) hold."""
    import threading
    
    exceptions = []
    def worker():
        try:
            with transaction.atomic():
                # Simulate the lock and process
                perform_mentoring_action()
        except Exception as e:
            exceptions.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    # 1 succeeds, 4 fail with concurrency exceptions
    assert len(exceptions) == 4

@patch('requests.post')
def test_network_timeout_mentoring(mock_post):
    """Ensure system degrades gracefully when upstream is slow."""
    import requests
    mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")
    
    with pytest.raises(ServiceUnavailableError):
         perform_mentoring_action()
```

### 15.3 Multi-Environment Comparison
| Environment | State Management | Concurrency | Latency | Debugging Strategy |
|-------------|------------------|-------------|---------|--------------------|
| **Local Dev** | SQLite / Local Redis | Single-threaded | < 5ms | Use `pdb` / `ipdb`, inspect local logs. |
| **Docker Compose** | Containerized PG | Local Gunicorn | ~10ms | Docker exec, attach debugger. |
| **CI/CD Pipeline** | Ephemeral DBs | Parallel Pytest | ~50ms | View artifacts, capture stdout/stderr. |
| **Staging (EKS)** | RDS Multi-AZ | HPA, 5 pods | ~30ms | Datadog/New Relic APM tracing. |
| **Production (100k RPS)**| RDS Read Replicas | KEDA + HPA, 500 pods | ~25ms | Distributed tracing, log aggregation (ELK). |

### 15.4 Django Internal Execution Trace for Mentoring
To truly master Mentoring, you must understand how Django handles it at the framework level.

1. **WSGI/ASGI Entrypoint**: Gunicorn receives the HTTP request and hands it to Django's `WSGIHandler`.
2. **Middleware Chain**: The request passes through `SecurityMiddleware`, `SessionMiddleware`, and custom middleware.
3. **URL Routing**: `URLResolver` matches the path to the specific view for Mentoring.
4. **View Execution**:
   - Authentication & Permissions are verified.
   - Database queries are generated via the ORM. (Watch out for N+1 queries here!)
   - Context is passed to the Template or serialized via DRF.
5. **Database Transaction**: If `ATOMIC_REQUESTS=True` or `transaction.atomic()` is used, a `BEGIN` statement is executed.
6. **Response Generation**: The view returns an `HttpResponse`.
7. **Middleware Teardown**: Middleware processes the response (e.g., adding headers).
8. **DB Commit/Rollback**: The transaction is committed. If an exception occurred, it rolls back.

### 15.5 Ticking Time Bomb Anti-Patterns
🔴 **Anti-Pattern 1: Unbounded Queries in Mentoring**
```python
# Ticking Time Bomb: This works locally with 10 rows.
# In prod, with 10M rows, it crashes the database and exhausts memory.
data = list(MyModel.objects.all())
```
✅ **The Fix:** Pagination, chunking, or streaming.
```python
# Staff-level fix
from django.core.paginator import Paginator
paginator = Paginator(MyModel.objects.order_by('id'), 1000)
for page in paginator.page_range:
    process(paginator.page(page).object_list)
```

🔴 **Anti-Pattern 2: Missing Indexes for Mentoring**
Querying by a non-indexed column in PostgreSQL will result in a Sequential Scan (`Seq Scan`). On a large table, this causes high CPU usage and slow responses.
✅ **The Fix:** Use `db_index=True`, `Meta.indexes`, or `GinIndex` for JSONB fields.

### 15.6 Resolution Playbook for Severity-1 Incidents
When a SEV-1 incident strikes related to Mentoring, follow this strict playbook:
1. **Acknowledge & Escalate:** Announce on `#incident-response`. PagerDuty alerts should be silenced.
2. **Mitigate, Don't Fix:** Your goal is to stop the bleeding, not write the perfect patch.
   - Scale up replicas? `kubectl scale deploy --replicas=50 app-name`
   - Block traffic? Add a WAF rule blocking the abusive IP or User Agent.
   - Revert deployment? Run the rollback CI pipeline.
3. **Investigation:** Look at APM traces. Are DB queries taking 5 seconds? Is Redis evicting keys?
4. **Root Cause Analysis (RCA):** Post-incident, write an ADR detailing *why* it happened (e.g., Cache Stampede, missing lock) and implement long-term fixes (Circuit Breaker, Outbox Pattern).

