# Django Mastery: Connection Management

## 1. Django Database Connection Lifecycle

By default, Django opens a **new database connection** for every HTTP request and closes it when the request finishes.

```text
[Request Starts]
      │
      ▼
Django connects to DB (TCP handshake, Postgres auth) 🐢 ~10-30ms penalty
      │
      ▼
Queries execute
      │
      ▼
`request_finished` signal fired
      │
      ▼
Connection closed
```

**The Problem:** At 1000 requests per second, Django does 1000 TCP handshakes and Postgres spawns 1000 backend processes per second. This destroys database CPU.

---

## 2. The `CONN_MAX_AGE` Setting

Django provides persistent connections via `CONN_MAX_AGE`.

```python
# settings.py
DATABASES = {
    \'default\': {
        \'ENGINE\': \'django.db.backends.postgresql\',
        \'NAME\': \'mydatabase\',
        # ...
        \'CONN_MAX_AGE\': 60,  # Keep connection alive for 60 seconds
    }
}
```

### Behavior Matrix
| `CONN_MAX_AGE` | Behavior | Usecase |
|----------------|----------|---------|
| `0` (Default)  | Close at end of request. | Low traffic, serverless, or dev. |
| `> 0` (e.g., 60)| Keep alive for N seconds. | Standard production deployments. |
| `None`         | Keep alive indefinitely. | Celery workers, background daemon threads. |

### The Danger of Persistent Connections
If you have 10 Gunicorn instances, each with 4 workers, each with 4 threads, you have `10 * 4 * 4 = 160` possible concurrent connections.
If PostgreSQL `max_connections` is set to 100, you will experience **Connection Exhaustion (OperationalError: FATAL: too many clients already)**.

---

## 3. Connection Pooling: PgBouncer

To solve connection exhaustion, use a connection pooler like **PgBouncer** sitting in front of PostgreSQL.

```text
[Django App (1000 connections)] 
        │
        ▼
[PgBouncer (Maintains 1000 frontend connections, routes to 50 backend connections)]
        │
        ▼
[PostgreSQL DB (50 actual connections, highly performant)]
```

### PgBouncer Pooling Modes

1. **Session Pooling (Default):** Connection assigned to client for the life of the connection. Does not solve Django\'s scaling problem.
2. **Transaction Pooling:** 🚀 **(Use this with Django)**. Connection is assigned only for the duration of a `BEGIN ... COMMIT` block. 
3. **Statement Pooling:** Multi-statement transactions are not allowed. Breaks Django.

### Django Configuration for Transaction Pooling
If using PgBouncer in Transaction mode, you MUST disable server-side prepared statements and handle `DISABLE_SERVER_SIDE_CURSORS` if using `iterator()`.

```python
# settings.py
DATABASES = {
    \'default\': {
        \'ENGINE\': \'django.db.backends.postgresql\',
        \'NAME\': \'mydatabase\',
        \'PORT\': 6432, # PgBouncer port
        \'CONN_MAX_AGE\': 0, # IMPORTANT: Let PgBouncer handle pooling, not Django!
        \'OPTIONS\': {
            # Required for PgBouncer Transaction Mode
            \'client_encoding\': \'UTF8\',
        }
    }
}
```

---

## 4. Production Incident: The Idle in Transaction Death

### Incident Report [SEV-1]
- **Symptom:** Database CPU low, but site is completely unresponsive. Application logs show `Timeout` and `OperationalError`.
- **Cause:** A developer put a 3rd party API call inside a database transaction block.
```python
with transaction.atomic():
    order = Order.objects.create(...)
    
    # 💣 The API is slow (5 seconds). 
    # The database connection is held open, doing nothing (Idle in Transaction).
    stripe_response = call_stripe_api() 
    
    order.stripe_id = stripe_response.id
    order.save()
```
  Under traffic, all available database connections (or PgBouncer connections) became locked waiting for Stripe.
- **Fix:** Move network I/O *outside* of transaction blocks.
```python
# 1. API Call
stripe_response = call_stripe_api()

# 2. Fast DB Transaction
with transaction.atomic():
    order = Order.objects.create(stripe_id=stripe_response.id, ...)
```

## 5. Production Checklist
- [ ] Determine max concurrent web workers/threads across all infrastructure.
- [ ] Ensure Postgres `max_connections` > Max Workers (if no pooler).
- [ ] Set up PgBouncer (Transaction mode) if Max Workers > 100.
- [ ] Never place network I/O (HTTP calls, S3 uploads) inside `transaction.atomic()`.
- [ ] Use `CONN_MAX_AGE = None` for Celery workers to avoid reconnect overhead per task.
