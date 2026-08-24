# 07. Advanced Queries in Django

## 1. Mental Model
```text
Python Variables ──▶ Processed in Application RAM
F() Expressions  ──▶ Pushed down to Database CPU (SQL level)
Q() Objects      ──▶ Pushed down to SQL WHERE/ON clauses as boolean trees
```

## 2. Why It Exists
Django abstracts basic CRUD, but complex business logic (e.g., "Give me users whose score > age * 2") would require fetching all rows into Python. `F()`, `Q()`, and `Window` functions push logic to the Database, operating closer to the data with C-level performance.

## 3. Internal Working
*   **`F()`**: Translates to an SQL column reference. `update(view_count=F('view_count') + 1)` translates to `SET view_count = view_count + 1`.
*   **`Q()`**: An implementation of the Node tree pattern. Bitwise operators (`|`, `&`, `~`) overload python dunder methods (`__or__`) to construct an SQL `WHERE` tree.

## 4. Basic vs 5. Production-Ready
### ❌ Basic (Race Conditions)
```python
# Ticking Time Bomb: Classic Race Condition
product = Product.objects.get(id=1)
product.stock -= 1
product.save() 
```

### ✅ Production-Ready (Atomic Updates)
```python
from django.db.models import F, Q, Case, When, Value, IntegerField

# 1. Atomic decrement preventing race conditions
Product.objects.filter(id=1).update(stock=F('stock') - 1)

# 2. Complex Q logic
active_premium = Q(is_active=True) & Q(subscription_tier='premium')

# 3. Conditional Aggregation
users = User.objects.annotate(
    status_code=Case(
        When(active_premium, then=Value(1)),
        When(is_active=True, then=Value(2)),
        default=Value(0),
        output_field=IntegerField()
    )
)
```

## 6. Anti-Patterns: Subquery Abuse
Using `Subquery` inside an `.annotate()` across 100,000 rows can be a performance disaster if the subquery isn't correlated properly using `OuterRef`, forcing a sequential scan instead of an index scan.

## 8. Debugging
🔴 **SYMPTOM**: Database Deadlock or Stale Data on Counters.
🔍 **CAUSE**: Updating counters using `save()` in memory.
🔧 **FIX**: Always use `F()` for relative updates, or explicitly lock rows with `select_for_update()`.

## 13. Production Checklist
- [ ] No arithmetic on model fields is done in Python (`+=`); `F()` is used instead.
- [ ] `Case/When` is utilized over python list comprehensions for derived attributes.
- [ ] Postgres Window Functions (`RowNumber()`, `Rank()`) are used instead of manual Python sorting/ranking.
