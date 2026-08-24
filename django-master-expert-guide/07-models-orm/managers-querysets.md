# 07. Managers & Custom QuerySets

## 1. Mental Model
```text
Model.objects ──▶ Manager ──▶ generates ──▶ QuerySet
      │                                       │
      └─ Contains model-level config          └─ Contains query chaining logic
```

## 2. Why It Exists
Fat models lead to unmaintainable spaghetti code. Custom `QuerySet` and `Manager` classes allow encapsulating business logic directly into the ORM layer, making it reusable, chainable, and testable.

## 3. Internal Working
When you call `Model.objects.active()`, the `Manager` delegates the call to the underlying `QuerySet`. By using `QuerySet.as_manager()`, Django dynamically creates a Manager class that copies all public methods of your QuerySet.

## 4. Basic vs 5. Production-Ready
### ❌ Basic
```python
# Logic scattered in views
active_posts = Post.objects.filter(is_deleted=False, status='published')
```

### ✅ Production-Ready
```python
class PostQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_deleted=False)
        
    def published(self):
        return self.filter(status='published')
        
    def with_author_stats(self):
        return self.select_related('author').annotate(
            author_post_count=models.Count('author__posts')
        )

# Use as_manager to bind to the model
class Post(models.Model):
    # ... fields ...
    objects = PostQuerySet.as_manager()
    
# Usage in view: Chainable and Clean
posts = Post.objects.active().published().with_author_stats()
```

## 6. Anti-Patterns: Soft Delete Default Managers
```python
# ❌ TICKING TIME BOMB
class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class Post(models.Model):
    objects = SoftDeleteManager() # Default manager!
```
**Why this is dangerous**: 
1. The Django Admin will silently hide deleted objects, making restoration impossible via UI.
2. If a `Comment` has a ForeignKey to a deleted `Post`, cascading deletes or related object accesses will throw `DoesNotExist` because the default manager hides it.

**Fix**: Always name custom managers explicitly (e.g., `active_objects`) or override `base_manager_name` and use standard `objects` for all rows.

## 13. Production Checklist
- [ ] Business logic is encapsulated in custom `QuerySet` methods.
- [ ] `QuerySet.as_manager()` is used instead of duplicating methods on Managers.
- [ ] Default manager (`objects`) NEVER filters out rows (e.g., soft deletes).


--------------------------------------------------------------------------------
# 🌟 PRINCIPAL/STAFF ENGINEER ENHANCEMENTS


## 🧠 Mental Model: The QuerySet Compilation Pipeline

At a principal engineering level, understanding Django's ORM requires internalizing the exact pipeline from a chained `.filter()` call down to the PostgreSQL wire protocol.

```text
========================================================================================
                      DJANGO 6.1 QUERYSET COMPILATION PIPELINE
========================================================================================

[ 1. Lazy Instantiation ]
User.objects.filter(is_active=True).exclude(email="")
       │
       ▼ (QuerySet._clone)
[ 2. AST Construction (django.db.models.sql.query.Query) ]
Builds the Abstract Syntax Tree. Node joins, WhereNodes, and Select nodes are added.
       │
       ▼ (Iteration, bool(), len(), list() triggers evaluation)
[ 3. Compilation (django.db.models.sql.compiler.SQLCompiler) ]
query.get_compiler(using=db).as_sql()
Translates AST to dialect-specific SQL string + parameters.
       │
       ▼ (django.db.backends.postgresql.base.DatabaseWrapper)
[ 4. Execution (psycopg3 / DBAPI 2.0) ]
Cursor creation, query execution.
       │
       ▼ (PostgreSQL Wire Protocol)
[ 5. PgBouncer / Connection Pooler ] (Transaction mode vs Session mode)
       │
       ▼
[ 6. PostgreSQL Engine ]
Parse -> Bind -> Plan -> Execute (Buffer Cache, B-Tree Traversal, Heap Fetch)
       │
       ▼ (Rows returned to Django)
[ 7. Model Instantiation (django.db.models.query.ModelIterable) ]
Result cache populated. Memory footprint expands heavily here.
```


## 💾 Memory Footprint: Model Instances vs Raw Tuples

Instantiating Django models is heavily CPU and memory bound. When fetching 100k rows, the difference between `.all()` and `.values_list()` is orders of magnitude.

```python
# django/db/models/query.py -> ModelIterable.__iter__
for row in compiler.results_iter(...):
    # This instantiation involves __init__, state tracking, signal setup
    obj = model_cls.from_db(db, init_list, row[model_fields_start:model_fields_end])
    yield obj
```

**Decision Matrix**:
| Approach | Memory/10k rows | CPU Cost | Use Case |
|---|---|---|---|
| `.all()` | ~45MB | High (Model `__init__`) | Need model methods, signals, save() |
| `.values()` | ~12MB | Medium (Dict alloc) | Need serialization via DRF |
| `.values_list()` | ~6MB | Low (Tuple alloc) | Passing bulk IDs or primitive data |
| `.iterator()` | ~10KB | Low (Generator) | Processing millions of rows |


## 🔬 Complete EXPLAIN (ANALYZE, BUFFERS) Breakdown

To achieve Staff-level performance, `django.db.connection.queries` is not enough. You must understand PostgreSQL's `EXPLAIN (ANALYZE, BUFFERS)`.

```sql
EXPLAIN (ANALYZE, BUFFERS) 
SELECT "users_user"."id", "users_user"."email" 
FROM "users_user" 
WHERE "users_user"."is_active" = true;

-- Output:
-- Index Scan using users_user_is_active_idx on users_user  (cost=0.42..154.21 rows=4821 width=42) (actual time=0.031..4.521 rows=4911 loops=1)
--   Index Cond: (is_active = true)
--   Buffers: shared hit=42 read=12 dirtied=0
-- Planning Time: 0.123 ms
-- Execution Time: 4.812 ms
```

**Annotated Costs & Buffers**:
- `cost=0.42..154.21`: First number is startup cost (time to return first row). Second is total cost (arbitrary units, typically based on sequential page fetches).
- `rows=4821`: The planner's *estimate* based on pg_statistic.
- `actual ... rows=4911`: Reality. If estimate and actual drift significantly, `ANALYZE users_user;` is needed.
- `Buffers: shared hit=42 read=12`: **CRITICAL METRIC**. 42 blocks were in RAM (hit). 12 blocks had to be fetched from disk/OS cache (read). High `read` indicates memory pressure or cold cache.


## 🚨 Real-World Production Incident Case Studies

### Incident 1: SerializerMethodField N+1 Collapsing DB
🔴 **SYMPTOM**: Database CPU spiked to 100%, PgBouncer queue maxed out, 502 Bad Gateway across the board during a marketing push.
🔍 **CAUSE**: A `SerializerMethodField` in a DRF serializer was querying a reverse foreign key relation for *every single item* in a 100-item paginated list.
🔧 **FIX**: 
```python
# BROKEN (Ticking Time Bomb)
class UserSerializer(serializers.ModelSerializer):
    total_orders = serializers.SerializerMethodField()
    def get_total_orders(self, obj):
        return obj.orders.count() # N+1 query executed here

# PRODUCTION-HARDENED
# 1. Annotate the QuerySet in the view
queryset = User.objects.annotate(total_orders_count=Count('orders'))
# 2. Use integer field in serializer
class UserSerializer(serializers.ModelSerializer):
    total_orders = serializers.IntegerField(source='total_orders_count', read_only=True)
```

### Incident 2: The `defer()` Deferred Attribute Cascade Storm
🔴 **SYMPTOM**: A background Celery task processing users triggered 50,000 microscopic queries in 10 seconds, causing a localized DB lockup.
🔍 **CAUSE**: `User.objects.defer('bio')` was used to save memory. Inside a utility function deep in the call stack, `user.bio` was accessed. Because it was deferred, Django silently issued a `SELECT bio FROM user WHERE id = X` for *every* user.
🔧 **FIX**: 
Never use `defer()` or `only()` unless you have 100% control over the instance's lifecycle and guarantee deferred fields won't be accessed. Use `.values()` for DTOs.

### Incident 3: Missing Composite Index leading to CPU Lockup
🔴 **SYMPTOM**: Sorting an API endpoint by `created_at` for a specific `tenant_id` took 8 seconds.
🔍 **CAUSE**: `Index(fields=['tenant_id'])` existed. But `ORDER BY created_at` caused a massive in-memory sort (Sort Method: external merge disk) in Postgres.
🔧 **FIX**: Added composite index: `Index(fields=['tenant_id', 'created_at'])`. This allowed Postgres to use a reverse index scan without sorting.


## 🚀 [DJANGO 6.1+] Deep Dive: `FETCH_RAISE` and `FETCH_PEERS`

Django 6.1 introduces revolutionary cursor control fetch modes directly exposed to the ORM, fixing years of memory-bloat issues with iterators.

### `FETCH_RAISE`
In high-concurrency environments, you often want to ensure a query is fully satisfied by cache or specific bounds. `FETCH_RAISE` instructs the DB wrapper to raise an exception if the result set exceeds expectations, preventing accidental massive table scans from crashing app servers.

### `FETCH_PEERS`
A mechanism specifically optimized for PostgreSQL 16+ cursors, allowing batch-fetching of contiguous tuples in the B-Tree leaf pages without repeatedly crossing the Python/C DBAPI boundary.

*Source Trace: `django/db/backends/postgresql/base.py`*
```python
# When FETCH_PEERS is enabled on the queryset:
with connection.cursor() as cursor:
    cursor.execute("DECLARE django_cursor SCROLL CURSOR FOR ...")
    # Instead of fetchmany(chunk_size), fetch peers leverages pg level batching
    cursor.execute("FETCH FORWARD 2000 FROM django_cursor")
```


## 🔌 Connection Management & PgBouncer

🔴 **SYMPTOM**: `OperationalError: FATAL: remaining connection slots are reserved for non-replication superuser connections`
🔍 **CAUSE**: `CONN_MAX_AGE=0` (default). Every HTTP request opens and closes a TCP connection to PostgreSQL. Under high load, connection churn exhausts DB connection slots and spikes DB CPU just for SSL handshakes.

### Production Setup
1. **Django Side**: `CONN_MAX_AGE=60` (Keep connections alive for 60 seconds).
2. **PgBouncer Side**: `pool_mode = transaction`.

**PgBouncer Pooling Modes Diagram**:
```text
[ Django App 1 ] ─(Conn A)─▶ │                 │ 
                             │ PgBouncer       │ ──(DB Conn 1)──▶ [ Postgres ]
[ Django App 2 ] ─(Conn B)─▶ │ (Transaction)   │ ──(DB Conn 2)──▶ [ Postgres ]
                             │                 │
```
In `transaction` mode, PgBouncer assigns a real DB connection to the Django app *only* for the duration of a transaction (e.g., `ATOMIC`). Once the transaction commits, the DB connection is returned to PgBouncer's pool, even if Django keeps `Conn A` open.


## 🌳 PostgreSQL B-Tree Index Traversal

Understanding exactly how PostgreSQL traverses an index when you run `.filter()` is mandatory for Staff engineers.

```text
                     [ Root Node ] (Page 0)
                      /                      (id < 500)            (id >= 500)
             /                            [ Internal Node ]              [ Internal Node ]
      /           \                  /           (id < 250)    (id >= 250)      (id < 750)    (id >= 750)
   /                 \              /                 [Leaf Page 1]  [Leaf Page 2]  [Leaf Page 3]  [Leaf Page 4]
(IDs 1-249)    (IDs 250-499)  (IDs 500-749)  (IDs 750-1000)
   │
   ▼ (TID: Block/Offset)
[ Heap Tuple (Actual Row Data) ]
```

When you do `User.objects.filter(id=250)`, Postgres:
1. Reads Root Node (Cache hit, `shared_blks_hit`).
2. Follows pointer to Internal Node.
3. Follows pointer to Leaf Page 2.
4. Reads the TID (Tuple Identifier).
5. Fetches the actual row from the Heap (Unless it's an Index-Only Scan).


## 🔎 Internal Source Traces

### 1. `django/db/models/query.py` (`QuerySet._clone`)
```python
def _clone(self):
    # This is why QuerySets are chainable but immutable
    c = self.__class__(model=self.model, query=self.query.clone(), using=self._db, hints=self._hints)
    c._sticky_filter = self._sticky_filter
    c._for_write = self._for_write
    c._prefetch_related_lookups = self._prefetch_related_lookups[:]
    c._known_related_objects = self._known_related_objects
    c._iterable_class = self._iterable_class
    c._fields_for_select = self._fields_for_select
    return c
```

### 2. `django/db/models/sql/compiler.py` (`SQLCompiler.execute_sql`)
```python
def execute_sql(self, result_type=MULTI, chunked_fetch=False, chunk_size=GET_ITERATOR_CHUNK_SIZE):
    # Compiles the AST to SQL
    sql, params = self.as_sql()
    
    # Executes via the DB wrapper
    cursor = self.connection.cursor()
    cursor.execute(sql, params)
    
    if result_type == MULTI:
        return cursor
```


## 🛡️ Pytest Query Count Assertions (Preventing Regressions)

Staff-level teams don't just fix N+1s; they write tests that fail the CI pipeline if an N+1 is reintroduced.

```python
import pytest

@pytest.mark.django_db
def test_user_list_api_query_count(client, django_assert_max_num_queries):
    # Setup
    UserFactory.create_batch(100)
    
    # Assert query counts stay bounded regardless of row count
    # 1 query for auth, 1 for COUNT(), 1 for users + prefetched data
    with django_assert_max_num_queries(3):
        response = client.get('/api/users/')
        
    assert response.status_code == 200
    assert len(response.json()['results']) == 100
```

