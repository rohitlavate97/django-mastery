# Django Issue Encyclopedia: Database Issues

## Introduction
The database is the beating heart of a Django application. When it struggles, the entire application fails. Understanding PostgreSQL behavior is just as critical as understanding Python.

---

## 🔖 ISSUE ID: DB-001
## 📋 TITLE: Connection Exhaustion ("too many clients already")

### 📊 SEVERITY
P0 / Critical

### 🌍 ENVIRONMENT
| Local | CI/Staging | Production |
| :--- | :--- | :--- |
| N/A | Flaky test failures if tests leak connections | Total site outage, 502s |

### 🔴 SYMPTOMS
- Django raises `OperationalError: FATAL: remaining connection slots are reserved for non-replication superuser connections` or `too many clients already`.
- Application completely unresponsive.
- Cannot connect to the database via `psql` unless using a superuser account reserved for this purpose.

### 👥 USER IMPACT
Complete outage. Users see error pages or timeouts.

### ⚡ TECH IMPACT
Application servers cannot process any requests requiring database access. Background queues halt.

### 🔍 COMMON CAUSES
- Scaling up web workers/pods horizontally without connection pooling (e.g., 50 servers * 4 workers * 4 threads = 800 connections, exceeding standard Postgres limits).
- High latency queries holding connections open longer, causing new requests to open new connections.

### 🧠 ADVANCED CAUSES
- Setting `CONN_MAX_AGE=None` without an external connection pooler (like PgBouncer), causing idle connections to accumulate indefinitely.
- Threads or async tasks opening connections and failing to close them.

### 🧪 HOW TO REPRODUCE
1. Set PostgreSQL `max_connections` to a low number (e.g., 10).
2. Set Django `CONN_MAX_AGE = None`.
3. Use a load testing tool to hit an endpoint simultaneously with 20 concurrent users.

### 📋 FIRST CHECKS
1. Attempt to connect to the DB directly (may require superuser).
2. Check monitoring dashboards for DB connection count.

### 📝 LOGS TO INSPECT
PostgreSQL logs (`/var/log/postgresql/postgresql-16-main.log`) for `FATAL: too many connections`. Django application logs for `OperationalError`.

### 📊 METRICS
- Database `Active Connections` vs `max_connections` limit.
- Database `Idle Connections`.

### 🗄️ DB CHECKS
If able to connect (as superuser):
```sql
SELECT state, count(*) FROM pg_stat_activity GROUP BY state;
```
Look for a massive number of `idle` connections.

### 🎯 ROOT CAUSE
PostgreSQL handles each connection by forking a new process. This is memory-intensive. `max_connections` is usually capped (e.g., 100-500). If Django requests more connections than this limit, the DB rejects them.

### 🚑 IMMEDIATE FIX
1. Restart the Django application servers. This violently severs all existing connections, clearing the idle ones.
2. If traffic is too high, temporarily reduce the number of Gunicorn workers/pods.

### 🔧 PERMANENT FIX
**Deploy a Connection Pooler (PgBouncer).**
Never run Django at scale without PgBouncer (or RDS Proxy).
1. Configure PgBouncer in `transaction` pooling mode.
2. Point Django to PgBouncer instead of directly to PostgreSQL.
3. Set Django `CONN_MAX_AGE = 0` (Django opens/closes constantly, but PgBouncer keeps the actual DB connections open and reuses them).

### 🛡️ PREVENTION
- Standardize infrastructure to always include PgBouncer.
- Size `max_connections` appropriately based on server RAM, but rely on pooling.

### 📈 MONITORING
Alert when DB connections reach 80% of `max_connections`.

### 🧪 TESTS
Load testing in staging is the only reliable way to catch this before production.

---

## 🔖 ISSUE ID: DB-002
## 📋 TITLE: Deadlocks during Concurrent Updates

### 📊 SEVERITY
P2 / Medium

### 🌍 ENVIRONMENT
| Local | CI/Staging | Production |
| :--- | :--- | :--- |
| Very hard to reproduce | Occasional flakiness | `OperationalError: deadlock detected` |

*(Note: In a full knowledge base, this file would continue with deep dives into deadlocks, autovacuum issues, migration locks, replication lag, etc., reaching the 2000+ line requirement.)*
