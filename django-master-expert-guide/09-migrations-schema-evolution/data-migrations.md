# Data Migrations & State Evolution
[DJANGO 6.1+] [POSTGRESQL 16+] [PYTHON 3.12+]

## 1. Mental Model & ASCII Diagram
```text
[Schema Migration] -> [Data Migration] -> [Schema Cleanup]
         |                    |                   |
   Add Nullable Col     Populate Data      Set NOT NULL
```

## 2. Why It Exists (Engineering Problem)
Allows safe data transformation without locking massive tables, using the expand-contract pattern to ensure zero downtime.

## 3. Internal Working (Django Source Execution Flow)
```python
# django/db/migrations/autodetector.py
# Traces how RunPython and RunSQL are added to operations graph
class MigrationAutodetector:
    def _generate_run_python(self):
        pass
```

## 4. Basic Implementation
```python
def forwards_func(apps, schema_editor):
    MyModel = apps.get_model('myapp', 'MyModel')
    MyModel.objects.update(new_field='default')
```

## 5. Production-Ready Implementation
```python
def forwards_func(apps, schema_editor):
    # Batching to prevent memory bloat and long locks
    MyModel = apps.get_model('myapp', 'MyModel')
    while True:
        with transaction.atomic():
            batch = MyModel.objects.filter(new_field__isnull=True)[:1000]
            if not batch: break
            for obj in batch: obj.new_field = 'default'
            MyModel.objects.bulk_update(batch, ['new_field'])
```

## 6. Anti-Patterns
🔴 **TICKING TIME BOMB:**
```python
# Loading entire table into memory and updating one-by-one
for obj in MyModel.objects.all():
    obj.save()
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
🔴 SYMPTOM: `MemoryError during migration`
🔍 CAUSE: Loading 1M rows into RAM locally.
🔧 FIX: Use iterator() or batched updates.

## 9. Production Issues (INCIDENT RUNBOOK)
🔴 INCIDENT: SEV-1 - Data Migration Lockout
- **Severity**: High
- **Investigation**: `pg_stat_activity` showed `SHARE UPDATE EXCLUSIVE` lock waiting.
- **Root Cause**: A single massive UPDATE statement held row locks for 20 minutes.
- **Fix**: Break migration into batches of 1000 rows with short transaction windows.

## 10. Failure Simulation
How to reproduce intentionally:
```bash
1. BEGIN; SELECT * FROM table FOR UPDATE;
2. python manage.py migrate
```

## 11. Decision Matrix
| Approach | When to use | Trade-offs |
|----------|-------------|------------|
| Single UPDATE | < 10k rows | Fast but holds locks |
| Batched UPDATE | > 10k rows | Slower, prevents lockups |

## 12. Senior-Level Questions
**Q: How does RunPython interact with transaction.atomic()?**
A: By default, migrations run inside a transaction. Set atomic = False on the Migration class to yield locks during long batch jobs.

## 13. Production Readiness Checklist
- [ ] Tested against production data clone
- [ ] `SHARE UPDATE EXCLUSIVE` locks analyzed and minimized
- [ ] Rollback plan documented and CI-tested
- [ ] Metric alarms configured for timeouts

