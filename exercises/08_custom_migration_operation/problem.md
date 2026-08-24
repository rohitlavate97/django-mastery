# Exercise 08: Zero-Downtime Index Creation

## The Problem
Adding an index to a large PostgreSQL table blocks writes to that table for the duration of the index build. This can cause application downtime. PostgreSQL supports `CREATE INDEX CONCURRENTLY` which doesn't block writes, but Django's standard `AddIndex` operation runs inside a transaction (which prevents concurrent index creation) and uses the standard blocking `CREATE INDEX`.

## Your Task
Create a custom Django migration operation `SafeAddIndexConcurrently` to add indexes without downtime.

### Requirements
1. **Migration Operation**: Inherit from `django.db.migrations.operations.base.Operation` or similar.
2. **Atomic**: The operation must explicitly declare `atomic = False` so it runs outside a transaction.
3. **Lock Timeout**: Set a brief `lock_timeout` (e.g., '2s') before executing the index creation, so if it needs a lock and is blocked, it fails quickly instead of queueing up other queries.
4. **SQL Execution**: Use `CREATE INDEX CONCURRENTLY` in the forward execution.
