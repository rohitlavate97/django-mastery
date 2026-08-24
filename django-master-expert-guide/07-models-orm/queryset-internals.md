# 07. QuerySet Internals & Lazy Evaluation

## 1. Mental Model
```text
QuerySet (Un-evaluated) 
  │ .filter() ──▶ Returns NEW QuerySet (Cloned)
  │ .exclude() ─▶ Returns NEW QuerySet (Cloned)
  ▼
[ Evaluation Trigger ] (list(), iteration, len(), bool())
  │
  ▼
SQL Compiler (django.db.models.sql.compiler)
  │
  ▼
Database Execution ──▶ result cache populated
```

## 2. Why It Exists
Fetching data immediately on every `.filter()` would destroy database performance. Lazy evaluation allows developers to chain complex conditions, passing QuerySets around before compiling a single, optimized SQL query.

## 3. Internal Working: `QuerySet._clone()`
A `QuerySet` holds a `django.db.models.sql.query.Query` object. Every time you call a chainable method, Django calls `_clone()`, which deepcopies the underlying `Query` AST (Abstract Syntax Tree). 

When you evaluate (`__iter__`), Django calls `self.query.get_compiler(using=self.db).execute_sql()`.

## 4. Basic vs 5. Production-Ready
### ❌ Basic
```python
# Bad: Evaluates QuerySet multiple times
active_users = User.objects.filter(is_active=True)
if active_users:         # EVALUATION 1: bool() runs query
    for user in active_users: # EVALUATION 2 (Cached, but bad pattern)
        print(user)
print(len(active_users)) # Uses cache
```

### ✅ Production-Ready
```python
# Good: using .exists() and .count() selectively
active_users = User.objects.filter(is_active=True)
if active_users.exists(): # Query 1: SELECT 1 FROM user WHERE is_active LIMIT 1
    # Do something
    pass

# For processing large datasets:
for user in active_users.iterator(chunk_size=2000): # Bypasses _result_cache, saves memory
    process(user)
```

## 6. Anti-Patterns: The `len()` Trap
Using `len(queryset)` forces the entire queryset to load into memory and populate `_result_cache`. If you only need the count, ALWAYS use `.count()` which compiles to `SELECT COUNT(*)`.

## 8. Debugging 
🔴 **SYMPTOM**: OOM (Out of Memory) Kills in production cron jobs.
🔍 **CAUSE**: `for item in MassiveModel.objects.all():` loaded 5 million rows into the `_result_cache`.
🔧 **FIX**: Swapped to `.iterator()`.

## 13. Production Checklist
- [ ] `len()` is never used on unevaluated QuerySets.
- [ ] `.exists()` is used for boolean checks.
- [ ] `.iterator()` is used for batch processing > 10,000 rows.
- [ ] Checked `CaptureQueriesContext` in tests to ensure QuerySets are not evaluated prematurely.
