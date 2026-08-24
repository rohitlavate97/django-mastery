# Django Mastery Performance Benchmarks

This directory contains standalone, runnable performance benchmarks demonstrating real-world latency, throughput, and memory characteristics of various Django and PostgreSQL patterns.

## Running the Benchmarks

```bash
python3 benchmarks/benchmark_suite.py
```

## Key Benchmarked Scenarios

1. **ORM Relational Fetching**:
   - Compares naive N+1 queries with network roundtrip latency against `select_related()` (Single SQL JOIN) and `prefetch_related()`.
2. **Database Pagination Scaling**:
   - Compares `OFFSET` / `LIMIT` deep scans on large tables (O(N) cost) against `CursorPagination` (Indexed Seek, O(log N) constant time).
3. **Concurrency & Atomicity**:
   - Compares Python-side read-modify-write patterns against atomic database-level `F()` expressions.
