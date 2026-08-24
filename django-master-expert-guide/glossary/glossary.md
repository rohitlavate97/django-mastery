# Django Mastery: Comprehensive Glossary

A deep-dive technical dictionary for Django, Python, PostgreSQL, and web infrastructure.

## A
- **ASGI (Asynchronous Server Gateway Interface)**: The spiritual successor to WSGI. It provides a standard interface between async-capable Python web servers, frameworks, and applications. Required for Django Channels and async views.
- **AppRegistry**: Django's internal state machine (`django.apps.registry.Apps`). It loads and holds references to all models. If you interact with models before this is populated, you get `AppRegistryNotReady`.

## B
- **B-Tree Index**: The default PostgreSQL index type. Excellent for exact matches, ranges, and sorting.
- **Bulk Create (`bulk_create`)**: Django ORM method that compiles multiple object creations into a single `INSERT` SQL statement, bypassing `save()` and signals.

## C
- **Celery**: An asynchronous task queue/job queue based on distributed message passing. Essential for offloading heavy tasks from web requests.
- **CONN_MAX_AGE**: Django setting that determines the lifetime of a database connection. `0` closes it at the end of each request (slow). `None` implies unlimited (risks leaks). A value like `60` enables connection pooling natively.
- **Content Types Framework**: A generic Django app (`django.contrib.contenttypes`) that tracks all models in the project, allowing generic relations (linking one model to any other model dynamically).

## D
- **Deferred Fields (`.defer()`, `.only()`)**: QuerySet methods to explicitly exclude or include specific columns in the SQL `SELECT` statement, preventing large text/binary blobs from loading into memory.
- **Django REST Framework (DRF)**: The standard library for building Web APIs in Django. It provides serialization, viewsets, authentication, and throttling.

## E
- **Expand & Contract Pattern**: A zero-downtime deployment strategy for schema changes. Involves multiple non-breaking deployments (add column, migrate data, swap usage, drop old column) instead of one breaking change.
- **EXPLAIN ANALYZE**: PostgreSQL command to profile a query, showing the execution plan and actual execution times. Critical for debugging slow Django queries.

## F
- **F() Expressions**: Django ORM objects representing the value of a database column. Used to perform database-level atomic operations (e.g., `views = F('views') + 1`) to prevent race conditions.

## G
- **Gunicorn**: A Python WSGI HTTP Server for UNIX. It manages worker processes that actually run the synchronous Django code.
- **Gin Index (Generalized Inverted Index)**: PostgreSQL index type highly optimized for full-text search, arrays, and JSONB fields.

## M
- **Middleware**: A framework of hooks into Django's request/response processing. It’s a light, low-level "plugin" system for globally altering Django’s input or output.
- **Migrations**: Django's way of propagating changes made to models (adding a field, deleting a model, etc.) into the database schema.
- **MVCC (Multi-Version Concurrency Control)**: PostgreSQL's mechanism for handling concurrent transactions. It creates row versions so readers don't block writers, and writers don't block readers.

## N
- **N+1 Query Problem**: A performance anti-pattern where an application executes 1 database query to fetch a list of N objects, then executes N additional queries to fetch a related attribute for each object. Fixed using `select_related` and `prefetch_related`.

## P
- **PgBouncer**: A lightweight connection pooler for PostgreSQL. Sits between Django and DB to handle thousands of incoming connections while maintaining a small set of real DB connections.
- **Prefetch Related**: Django ORM method that solves the N+1 problem for ManyToMany and reverse ForeignKey relationships. It performs a separate SQL query and joins them in Python memory.

## Q
- **Q Objects**: Used in Django ORM to encapsulate keyword arguments for complex database queries (e.g., `OR` statements: `Q(name="A") | Q(name="B")`).

## R
- **Reverse Relation**: The implicit relationship created by Django on the target model of a `ForeignKey` or `ManyToManyField`. Accessed via `<modelname>_set` or a custom `related_name`.

## S
- **Select Related**: Django ORM method that solves the N+1 problem for ForeignKey and OneToOne relationships by performing an SQL `JOIN` and including the related fields in the `SELECT` statement.
- **Signals**: Django's event dispatcher. Allows decoupled applications to get notified when actions occur elsewhere (e.g., `post_save`, `pre_delete`). Use sparingly as they obscure control flow.

## T
- **Transaction.atomic**: A context manager / decorator that wraps a block of code in a database transaction. If an exception is raised, the database rolls back all changes in the block.

## U
- **Uvicorn**: A lightning-fast ASGI server implementation, using `uvloop` and `httptools`. Used to serve async Django apps in production.

## W
- **WSGI (Web Server Gateway Interface)**: The standard interface for synchronous Python web applications. Usually served via Gunicorn or uWSGI.
