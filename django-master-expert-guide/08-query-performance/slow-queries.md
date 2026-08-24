# Django Mastery: Slow Queries & Indexing

## 1. Diagnosing Slow Queries: EXPLAIN

Before fixing a slow query, you must see exactly what the database is doing. Django provides `explain()`.

### Basic Usage
```python
# Python
queryset = User.objects.filter(email__endswith=\'@gmail.com\')
print(queryset.explain(analyze=True))
```

### Reading PostgreSQL EXPLAIN ANALYZE [POSTGRESQL-ONLY]

```text
QUERY PLAN
-----------------------------------------------------------------------------------------------------------------
 Seq Scan on auth_user  (cost=0.00..345.00 rows=100 width=36) (actual time=0.015..5.123 rows=150 loops=1)
   Filter: ((email)::text ~~ \'%@gmail.com\'::text)
   Rows Removed by Filter: 9850
 Planning Time: 0.120 ms
 Execution Time: 5.150 ms
```

**Key Terms:**
- **Seq Scan (Sequential Scan):** 🔴 Bad for large tables. Reads every row from disk.
- **Index Scan:** 🟢 Good. Traverses the B-tree index, then fetches the row from the heap.
- **Index Only Scan:** 🚀 Best. The index contains all needed data (`include`), so PostgreSQL doesn\'t read the heap (table) at all.
- **Bitmap Heap/Index Scan:** 🟡 Combines multiple index lookups or handles medium selectivity.
- **cost=0.00..345.00:** Estimated cost (startup..total).
- **actual time=0.015..5.123:** Actual time in ms.
- **loops=1:** Number of times the node was executed. (Beware of Nested Loops with high inner loop counts).

---

## 2. Indexing Strategies for Django Models

### Single-Column B-Tree Index
```python
class UserProfile(models.Model):
    # db_index=True creates a standard B-tree index
    username = models.CharField(max_length=255, db_index=True) 
```

### Composite Indexes (The Rule of Thumb)
**Rule:** Equality first, then Range/Sort.

If you query: `filter(tenant_id=1, created_at__gte=\'2023-01-01\')`
```python
class Order(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    created_at = models.DateTimeField()

    class Meta:
        indexes = [
            # GOOD: tenant_id (Equality) first, created_at (Range) second
            models.Index(fields=[\'tenant_id\', \'created_at\']),
            
            # BAD: Range first stops index usage for subsequent fields
            # models.Index(fields=[\'created_at\', \'tenant_id\']),
        ]
```

### Partial Indexes (`condition`) [DJANGO 2.2+]
Indexes take up disk space and slow down `INSERT`/`UPDATE`. Partial indexes only index rows matching a `Q` object.

```python
class Task(models.Model):
    status = models.CharField(max_length=20) # \'pending\', \'done\', \'archived\'
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        indexes = [
            # We only query pending tasks, so don\'t index millions of archived ones!
            models.Index(
                fields=[\'assigned_to\'],
                condition=models.Q(status=\'pending\'),
                name=\'idx_pending_tasks\'
            )
        ]
```

### Covering Indexes (`include`) [DJANGO 3.2+] [POSTGRESQL-ONLY]
Allows an **Index Only Scan**.

```python
class Product(models.Model):
    sku = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        indexes = [
            # Query: Product.objects.filter(sku=\'ABC\').values(\'price\')
            # Reads only the index, doesn\'t touch the table!
            models.Index(
                fields=[\'sku\'], 
                include=[\'price\'],
                name=\'idx_sku_incl_price\'
            )
        ]
```

---

## 3. PostgreSQL Query Planning Pitfalls

### A. Statistics Out of Date
🔴 **SYMPTOM:** Query plan suddenly switches from Index Scan to Seq Scan.
🔍 **CAUSE:** PostgreSQL auto-analyze hasn\'t run recently. The planner thinks the table is small or data distribution has changed.
🔧 **FIX:** Run manual `ANALYZE`.
```sql
ANALYZE auth_user;
```

### B. Index Bloat
🔴 **SYMPTOM:** Index scans are slow. Index size on disk is larger than the table.
🔍 **CAUSE:** High churn (UPDATE/DELETE). MVCC leaves dead tuples in the index.
🔧 **FIX:** `REINDEX INDEX index_name CONCURRENTLY;`

### C. Function Calls Disabling Index Use
**BROKEN**
```python
# Translates to UPPER(email) = \'TEST@GMAIL.COM\'
# Standard B-tree on email cannot be used!
User.objects.filter(email__iexact=\'test@gmail.com\') 
```

**FIXED (Django 3.2+ Database Functions in Indexes)**
```python
from django.db.models.functions import Upper

class User(models.Model):
    email = models.EmailField()

    class Meta:
        indexes = [
            models.Index(Upper(\'email\'), name=\'idx_user_email_upper\')
        ]
```

---

## 4. Production Incident: The Like Button DDOS

### Incident Report [SEV-2]
- **Symptom:** Database CPU spiked to 100%. Site degraded.
- **Root Cause:** A developer added a "Top Liked Posts Today" widget on the homepage.
  The query: `Post.objects.filter(created_at__gte=today).order_by(\'-likes_count\')`
  There was an index on `created_at` and an index on `likes_count`.
  PostgreSQL chose a BitmapAnd, fetched millions of rows matching `created_at`, and then sorted them IN MEMORY (`SortMethod: external merge Disk`).
- **Fix:**
  1. Add composite index: `models.Index(fields=[\'-likes_count\', \'created_at\'])` (if querying by top likes within a range) OR cache the result heavily.
  2. Implement caching for the homepage widget with a 5-minute TTL.

## 5. Decision Matrix

| Query Type | Best Index Strategy | Note |
|------------|---------------------|------|
| `filter(a=1, b=2)` | Composite `(a, b)` | Order matters less if both equality. |
| `filter(a=1).order_by(\'b\')` | Composite `(a, b)` | Equality first, sort field second. |
| `filter(is_active=True, user=X)` | Partial Index on `user` where `is_active=True` | Saves massive space. |
| `filter(name__icontains=\'abc\')` | `GinIndex(OpClass(Upper(\'name\'), name=\'gin_trgm_ops\'))` | Requires `pg_trgm` extension. |
