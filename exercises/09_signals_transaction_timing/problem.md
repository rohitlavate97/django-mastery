# Exercise 09: Signals and Transaction Timing

## The Problem
A common bug in Django applications occurs when a `post_save` signal triggers a Celery task (like sending a welcome email). If the database transaction hasn't committed yet when the task starts executing on a worker, the worker might try to query the database for the new user and fail because the row doesn't exist yet (or the transaction might roll back, but the email still goes out).

## Your Task
Rewrite a naive `post_save` signal handler to use `transaction.on_commit()` to ensure the task is only queued *after* the transaction successfully commits.

### Requirements
1. **Signal Handler**: Create a receiver for `post_save` on a `User` model.
2. **On Commit**: Wrap the task enqueueing logic inside `transaction.on_commit()`.
3. **Rollback Safety**: Ensure that if the transaction is rolled back, the task is never triggered.
