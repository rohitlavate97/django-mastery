# PostgreSQL 16+ Tuning Cheat Sheet for Django Workloads

## 1. Hardware Sizing Formulas (`postgresql.conf`)

| Parameter | Recommended Formula | Example (32 GB RAM Server) | Purpose |
|---|---|---|---|
| `shared_buffers` | `RAM * 0.25` | `8GB` | Dedicated memory cache for PostgreSQL buffer pool |
| `effective_cache_size` | `RAM * 0.75` | `24GB` | Planner's assumption of available cache (shared_buffers + OS page cache) |
| `maintenance_work_mem` | `RAM * 0.05` (max 2GB) | `1.5GB` | Memory for `VACUUM`, `CREATE INDEX`, `ALTER TABLE` |
| `work_mem` | `(RAM - shared_buffers) / (max_connections * 3)` | `64MB` | Memory per sort/hash operation per query |
| `max_connections` | Keep small + use PgBouncer | `100 - 200` | Limits process memory overhead |
| `random_page_cost` | `1.1` (for NVMe/SSD) | `1.1` | Instructs planner that SSD random reads are nearly as fast as seq reads |
| `checkpoint_completion_target` | `0.9` | `0.9` | Smooths checkpoint I/O spikes across interval |
| `wal_buffers` | `16MB` | `16MB` | Buffer for unwritten WAL data |

---

## 2. Autovacuum Tuning for High-Write Django Tables

```ini
# Aggressive autovacuum to prevent table bloat and wraparound
autovacuum = on
autovacuum_max_workers = 4
autovacuum_naptime = 15s
autovacuum_vacuum_threshold = 50
autovacuum_vacuum_scale_factor = 0.05       # Trigger vacuum when 5% of rows change (default is 20%)
autovacuum_analyze_threshold = 50
autovacuum_analyze_scale_factor = 0.02      # Trigger analyze when 2% of rows change
autovacuum_vacuum_cost_limit = 1000         # Increase I/O budget before throttling
```

---

## 3. Essential Diagnostic Queries

### Top 5 Slowest Queries by Mean Execution Time
```sql
SELECT 
    query, 
    calls, 
    round(total_exec_time::numeric, 2) AS total_ms, 
    round(mean_exec_time::numeric, 2) AS mean_ms, 
    rows 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC 
LIMIT 5;
```

### Check Active Locks and Waiting Queries
```sql
SELECT 
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_statement,
    blocking_activity.query AS current_statement_in_blocking_process
FROM  pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

### Kill a Blocking Transaction PID
```sql
SELECT pg_terminate_backend(12345);
```
