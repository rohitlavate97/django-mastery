# Django Mastery: Database Migration Safety Checklist

Database migrations are the #1 cause of production downtime in Django apps. Follow these rules to ensure zero-downtime deployments.

## 1. Zero-Downtime Fundamentals

- [ ] **Expand & Contract Pattern**: Never rename or delete a column in a single deployment.
  1. *Deploy 1*: Add new column. Update code to write to both.
  2. *Deploy 2*: Backfill data to new column.
  3. *Deploy 3*: Change code to read/write only from new column.
  4. *Deploy 4*: Drop old column.
- [ ] **No Default Values on Existing Tables**: Adding a column with a `default` to a large table locks the table in older PostgreSQL versions. Use Django's DB default (`db_default`) if using Django 5.0+, or add nullable, backfill, then enforce NOT NULL.

## 2. Safety Checks (Pre-Commit / CI)

- [ ] **Migration Check**: CI runs `makemigrations --check` to catch missed migrations.
- [ ] **Linting migrations**: Use `django-migration-linter` to catch backward-incompatible operations.
- [ ] **Lock Timeouts**: Set a strict `lock_timeout` before running migrations in production to prevent deadlocks:
  ```sql
  SET lock_timeout TO '5s';
  ```

## 3. Heavy Operations (Data Migrations)

- [ ] **Batching**: Never use `.update()` or iterate over `.all()` in a data migration without batching. Use `.iterator(chunk_size=1000)` and `transaction.atomic()` around batches.
- [ ] **Custom SQL**: Use `migrations.RunSQL` with `state_operations` to create concurrent indexes (which Django `makemigrations` doesn't do safely by default without special care).
- [ ] **Concurrent Indexing**:
  ```python
  migrations.RunSQL(
      "CREATE INDEX CONCURRENTLY idx_name ON table(column);",
      reverse_sql="DROP INDEX idx_name;"
  )
  ```
  *Ensure `atomic=False` is set on the Migration class.*

## 4. Operational Readiness

- [ ] **Backup**: Trigger an automated snapshot before applying migrations to production.
- [ ] **Rollback Plan**: Always write the `reverse_sql` for `RunSQL` or the backward function for `RunPython`. Test the rollback locally (`manage.py migrate app_name <previous_migration>`).
