# Django Migration Internals & DAG
[DJANGO 6.1+] [POSTGRESQL 16+] [PYTHON 3.12+]

## 1. Mental Model & ASCII Diagram
```text
Migration DAG:
App1_0001_initial  ---> App1_0002_add_field
       |
       +--------------> App2_0001_initial
```

## 2. Why It Exists (Engineering Problem)
Maintains a deterministic history of database changes, resolving dependencies across apps to ensure consistent deployment environments.

## 3. Internal Working (Django Source Execution Flow)
```python
# django/db/migrations/executor.py
class MigrationExecutor:
    def migration_plan(self, targets, clean_start=False):
        # Builds a directed acyclic graph (DAG)
        plan = []
        for target in targets:
            plan.extend(self.loader.graph.backwards_plan(target))
        return plan
```

## 4. Basic Implementation
```python
class Migration(migrations.Migration):
    dependencies = [('app1', '0001_initial')]
    operations = [migrations.AddField(...)]
```

## 5. Production-Ready Implementation
```python
class Migration(migrations.Migration):
    atomic = False # Prevent long-running schema locks
    dependencies = [
        ('app1', '0001_initial'),
        ('app2', '0003_auto_x'),
    ]
    operations = [
        # Safe concurrent index creation
        migrations.AddIndexConcurrently(...)
    ]
```

## 6. Anti-Patterns
🔴 **TICKING TIME BOMB:**
```python
# Circular dependencies in migrations across apps
dependencies = [('app2', '0001_initial')]
# In app2: dependencies = [('app1', '0001_initial')]
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
🔴 SYMPTOM: `django.db.migrations.exceptions.CircularDependencyError`
🔍 CAUSE: Two apps point to each other's migrations in a loop.
🔧 FIX: Squash migrations or extract a common base migration.

## 9. Production Issues (INCIDENT RUNBOOK)
🔴 INCIDENT: SEV-1 - Broken Migration State
- **Severity**: High
- **Investigation**: `pg_stat_activity` showed `ACCESS EXCLUSIVE` lock waiting.
- **Root Cause**: A failed migration left the django_migrations table out of sync with actual DB schema.
- **Fix**: Manually delete the row from django_migrations and fake the migration.

## 10. Failure Simulation
How to reproduce intentionally:
```bash
1. Run a migration that raises an exception halfway.
2. Observe state mismatch.
```

## 11. Decision Matrix
| Approach | When to use | Trade-offs |
|----------|-------------|------------|
| manage.py migrate | Standard CI/CD | Automated |
| manage.py migrate --fake | Resolving desync | Risky manual intervention |

## 12. Senior-Level Questions
**Q: What happens when a migration fails in Postgres vs MySQL?**
A: Postgres supports DDL transactions, so a failed ALTER TABLE rolls back. MySQL does not, leaving the schema partially updated.

## 13. Production Readiness Checklist
- [ ] Tested against production data clone
- [ ] `ACCESS EXCLUSIVE` locks analyzed and minimized
- [ ] Rollback plan documented and CI-tested
- [ ] Metric alarms configured for timeouts

