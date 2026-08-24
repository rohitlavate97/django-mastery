# Django Mastery: Performance Review Checklist

## 1. Database & ORM Optimization

- [ ] **N+1 Queries**: Audit all endpoints and templates. Use `select_related()` for foreign keys/OneToOne, and `prefetch_related()` for ManyToMany/Reverse Foreign Keys.
- [ ] **Query Counts**: Enforce `assertNumQueries` in test suites for critical paths.
- [ ] **Selective Fetching**: Use `.only()`, `.defer()`, or `.values()` when fetching massive datasets but needing only a few columns.
- [ ] **Bulk Operations**: Replace iterative `save()` or `create()` loops with `bulk_create()`, `bulk_update()`.
- [ ] **Slow Query Log**: Enable PostgreSQL `log_min_duration_statement` (>500ms) and analyze logs with `pgbadger`.
- [ ] **Indexes**: Run `EXPLAIN ANALYZE` on slow queries. Add `db_index=True`, `Index()`, or `GinIndex()` as necessary. Ensure composite indexes match query `WHERE` clauses.

## 2. Caching Strategy

- [ ] **Template Caching**: Use `{% cache %}` fragment caching for complex, rarely-changing UI components.
- [ ] **View Caching**: Apply `@cache_page` for public, non-user-specific endpoints.
- [ ] **Data Caching**: Cache heavy computation or slow ORM results using `cache.get_or_set()`.
- [ ] **Cache Invalidation**: Verify invalidation logic triggers on model `post_save` or `post_delete` signals where data caching is used.

## 3. Asynchronous Tasks (Celery)

- [ ] **Offload I/O**: Move emails, report generation, and API calls to Celery tasks.
- [ ] **Payload Size**: Pass primitive IDs to Celery tasks (e.g., `user_id`), NOT full ORM instances.
- [ ] **Retry Logic**: Implement `autoretry_for` with exponential backoff on network-dependent tasks.

## 4. API & Serialization (Django REST Framework)

- [ ] **Serializer Method Fields**: Audit `SerializerMethodField`. Avoid DB queries inside them (they run per row).
- [ ] **Read-Only**: Use `read_only=True` aggressively.
- [ ] **Pagination**: Enforce pagination on ALL list endpoints (`PageNumberPagination` or `CursorPagination`).
- [ ] **JSON Rendering**: Consider faster JSON parsers/renderers like `orjson` via `drf-orjson-renderer` for heavy endpoints.

## 5. Web Server & Connection Pooling

- [ ] **PgBouncer**: Verify PgBouncer connection reuse. Prevent database connection limits from being exhausted.
- [ ] **Worker Profile**: Use async workers (Uvicorn) for heavy I/O workloads, or synchronous (Gunicorn Sync/Gevent) tuned properly.
- [ ] **Memory Leaks**: Ensure worker max requests are configured to gracefully restart workers and reclaim memory.
