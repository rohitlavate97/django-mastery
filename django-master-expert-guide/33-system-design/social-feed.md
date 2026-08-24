# Real-time Social Feed

## 1. Mental Model
```text
[Client] -> [System API] -> [Core Logic for Real-time Social Feed]
                                |
                   +------------+-----------+
                   |                        |
            [Database (PG)]          [Cache / Queue]
```
Fan-out-on-write vs Fan-out-on-read, Cursor pagination, Feed caching is highly applicable in this context. We must manage strict requirements around performance and code maintainability.

## 2. Why It Exists
Solving complex engineering problems requires specialized patterns. If we stick to default Django implementations for Fan-out-on-write vs Fan-out-on-read, Cursor pagination, Feed caching, we run into scaling limits (e.g., God Objects, DB bottlenecks, or tight coupling).

## 3. Internal Working
Under the hood, Django provides abstractions (like QuerySets or Signals), but for Real-time Social Feed, we must extend or bypass these.
1. The request flows into the API layer.
2. We evaluate constraints (e.g., Bounded Context, Rate Limit).
3. Database transactions are isolated where necessary.
4. Async events are emitted to message brokers.

## 4. Basic Implementation
```python
# Basic approach (often naive but works for prototypes)
def simple_real_time_social_feed_handler(data):
    # Perform basic validation
    if not data:
        raise ValueError("Invalid data")
    
    # Process core logic
    result = process_data(data)
    
    return result
```

## 5. Production-Ready Implementation
```python
# Production-ready approach (handles edge cases, concurrency, locking)
import logging
from django.db import transaction

logger = logging.getLogger(__name__)

class Real-timeSocialFeedManager:
    @staticmethod
    def execute_robustly(data: dict):
        try:
            with transaction.atomic():
                # [POSTGRESQL-ONLY] Use select_for_update() if mutating shared state
                # Process strictly within bounded domain or pattern
                result = advanced_processing(data)
                
            # Fire domain events / Outbox pattern
            transaction.on_commit(lambda: publish_event(result))
            return result
        except Exception as e:
            logger.error(f"Critical failure in Real-time Social Feed: {e}")
            raise
```

## 6. Anti-Patterns (Ticking Time Bombs)
- **Shared DBs without boundaries:** Directly querying other microservices' tables.
- **Synchronous External Calls:** Making network calls to APIs inside a database transaction.
- **Ignoring idempotency:** Allowing retries to double-charge or duplicate data.

## 7. Environment-Specific Behavior
| Environment | Behavior | Note |
|-------------|----------|------|
| Local (Docker) | Minimal latency | Tests might pass but fail in staging |
| Prod (Postgres/Redis) | High concurrency | Lock contention, memory eviction limits apply |

## 8. Local Development Issues
🔴 **SYMPTOM:** Connection timeouts or missing cache keys.
🔍 **CAUSE:** Local Redis/DB is misconfigured or out of memory.
🔧 **FIX:** Use Docker Compose with memory limits and exact production versions.

## 9. Production Issues
🔴 **INCIDENT:** Severe performance degradation during peak load.
- **Severity:** High
- **Investigation:** Connections maxed out because DB locks were held too long.
- **Root Cause:** External HTTP call placed inside `transaction.atomic()`.
- **Fix:** Move HTTP calls outside the atomic block or into Celery tasks.

## 10. Failure Simulation
To test resilience, inject faults:
```bash
# Intentionally block a table to test timeouts
LOCK TABLE target_table IN EXCLUSIVE MODE;
# Run load test to ensure application handles 503s gracefully
```

## 11. Decision Matrix
| Strategy | When to use | Pros | Cons |
|----------|-------------|------|------|
| Default Django | Prototyping | Fast delivery | Technical debt |
| Real-time Social Feed Pattern | Complex domains | Decoupling | High initial overhead |

## 12. Senior-Level Questions
**Q: How do you handle backward compatibility during migrations for this pattern?**
A: Use the expand-and-contract pattern. First, write to both old and new schemas. Then, migrate reads. Finally, drop the old schema.

**Q: What about distributed transactions?**
A: Avoid Two-Phase Commit (2PC) if possible. Use the Saga pattern with compensating transactions.

## 13. Production Checklist
- [ ] Load testing completed up to 3x expected peak.
- [ ] Idempotency keys enforced on all mutating endpoints.
- [ ] Proper indexes added to PostgreSQL.
- [ ] Redis memory eviction policies reviewed (e.g., `allkeys-lru`).
- [ ] Alerting configured for error rate spikes.
