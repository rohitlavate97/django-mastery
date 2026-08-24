# Migration Conflicts - Deep Dive
[DJANGO 6.1+] [POSTGRESQL 16+] [PYTHON 3.12+]

## 1. Mental Model & ASCII Diagram
```text
Transaction A: Locks Row 1 ---> Tries to lock Row 2
Transaction B: Locks Row 2 ---> Tries to lock Row 1
       💥 DEADLOCK DETECTED (Postgres kills one)
```

## 2. Why It Exists (Engineering Problem)
Concurrent systems inevitably have racing requests. Deadlock detection prevents the system from halting completely by aborting one transaction.

## 3. Internal Working (Django Source Execution Flow)
```python
# django/db/transaction.py
# Context manager handling savepoints and commits
class Atomic(ContextDecorator):
    def __enter__(self):
        connection.set_autocommit(False)
        if connection.in_atomic_block:
            self.savepoint = connection.savepoint()
```

## 4. Basic Implementation
```python
with transaction.atomic():
    user = User.objects.select_for_update().get(id=1)
    account = Account.objects.select_for_update().get(id=user.account_id)
```

## 5. Production-Ready Implementation
```python
with transaction.atomic():
    # Always lock in consistent order (e.g., by ID)
    ids = sorted([1, 2])
    items = list(Item.objects.select_for_update().filter(id__in=ids))
    for item in items:
        item.balance -= 10
        item.save()
```

## 6. Anti-Patterns
🔴 **TICKING TIME BOMB:**
```python
# Unordered locking based on dynamic inputs
Account.objects.select_for_update().get(id=from_id)
Account.objects.select_for_update().get(id=to_id)
```

## 7. Environment-Specific Behavior
| Environment | Behavior | Risk Level |
|-------------|----------|------------|
| Local | SQLite/Postgres dev | Low |
| Docker | Containerized DB | Low |
| CI | Fresh DB per run | Low |
| Staging | Clone of Prod | Medium |
| Production | Live traffic | High |

## 8. Local Development Issues
🔴 SYMPTOM: `Random 500 errors in tests.`
🔍 CAUSE: Pytest workers hitting deadlocks on concurrent test execution.
🔧 FIX: Enforce sorted ID locking.

## 9. Production Issues (INCIDENT RUNBOOK)
🔴 INCIDENT: SEV-1 - Deadlock during Flash Sale
- **Severity**: High
- **Investigation**: `pg_stat_activity` showed `RowExclusiveLock` lock waiting.
- **Root Cause**: Multiple users buying the same overlapping cart items in different orders.
- **Fix**: Sort item IDs before `select_for_update()`.

## 10. Failure Simulation
How to reproduce intentionally:
```bash
T1: BEGIN; SELECT * FROM t WHERE id=1 FOR UPDATE; SELECT * FROM t WHERE id=2 FOR UPDATE;
T2: BEGIN; SELECT * FROM t WHERE id=2 FOR UPDATE; SELECT * FROM t WHERE id=1 FOR UPDATE;
```

## 11. Decision Matrix
| Approach | When to use | Trade-offs |
|----------|-------------|------------|
| select_for_update | Pessimistic locking | Can deadlock if unordered |
| Optimistic Locking | High read, low write | Requires retry logic |

## 12. Senior-Level Questions
**Q: How does Postgres resolve a deadlock?**
A: After `deadlock_timeout` (usually 1s), Postgres checks the wait graph. If a cycle exists, it aborts the transaction that requires the least effort to rollback, throwing a `DeadlockDetected` error.

## 13. Production Readiness Checklist
- [ ] Tested against production data clone
- [ ] `RowExclusiveLock` locks analyzed and minimized
- [ ] Rollback plan documented and CI-tested
- [ ] Metric alarms configured for timeouts

