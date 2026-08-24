# Django In-Memory Interactive Sandbox

A zero-configuration, standalone Python environment for experimenting with Django ORM compilation, transaction savepoints, and SQL profiling without configuring a database server.

## Quickstart

Run with `uv` (recommended):
```bash
uv run --with django python sandbox/sandbox_app.py
```

Or within an existing virtual environment:
```bash
python sandbox/sandbox_app.py
```

## Features Demonstrated
1. **Dynamic Model Creation**: Spawns in-memory SQLite tables dynamically with `connection.schema_editor()`.
2. **Real-time SQL Inspection**: Captures every executed query and parameter using Django's internal `CaptureQueriesContext`.
3. **Transaction SAVEPOINT Tracing**: Shows how nested `transaction.atomic()` creates, rolls back, and releases savepoints.
