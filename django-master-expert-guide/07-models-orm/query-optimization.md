# 07. Query Optimization

## 1. Mental Model
```text
Without Optimization (N+1 Problem)
Book.objects.all() ──▶ SELECT * FROM book; (1 query)
  book1.author     ──▶ SELECT * FROM author WHERE id=1; (N queries)
  
With Optimization (select_related)
Book.objects.select_related('author') 
  ──▶ SELECT book.*, author.* FROM book INNER JOIN author ON ... (1 query total)
```

## 2. Why It Exists
ORMs map rows to objects. Accessing a foreign key attribute requires the object. Without optimization, the ORM issues a new query for every attribute access. `select_related` and `prefetch_related` resolve this.

## 3. Internal Working
*   **`select_related`**: Modifies the `SQLCompiler` to include `JOIN` clauses and fetches all data in a single SQL round-trip. Works for ForeignKey and OneToOne.
*   **`prefetch_related`**: Executes the primary query, then executes a separate query for the related objects (`SELECT * FROM table WHERE id IN (...)`), and stitches them together in Python. Works for M2M and Reverse ForeignKeys.

## 4. Basic vs 5. Production-Ready
### ❌ Basic (The N+1 Landmine)
```python
def get_books():
    books = Book.objects.all()
    return [{"title": b.title, "author": b.author.name} for b in books] # N+1 queries!
```

### ✅ Production-Ready
```python
from django.db.models import Prefetch

def get_books_optimized():
    # 1. select_related for forward FK
    # 2. Prefetch object for advanced M2M filtering
    active_reviews = Review.objects.filter(is_published=True)
    
    books = Book.objects.select_related('author', 'publisher').prefetch_related(
        Prefetch('reviews', queryset=active_reviews, to_attr='active_review_list')
    )
    
    result = []
    for b in books:
        # Uses python memory, NO DB QUERIES!
        result.append({
            "title": b.title,
            "author": b.author.name,
            "reviews": [r.rating for r in b.active_review_list] 
        })
    return result
```

## 6. Anti-Patterns: Massive JOINs
```text
🔴 SYMPTOM: Database CPU 100%, high memory usage.
🔍 CAUSE: .select_related('a', 'b', 'c', 'd', 'e')
```
JOINs multiply data. Fetching 10 tables in one `select_related` forces the DB to send massive Cartesian product rows over the network. 
**Fix:** Split deep graphs into `prefetch_related` to let Python do the mapping.

## 7. `only()` and `defer()`
Use `only()` to restrict selected columns.
**DANGER**: If you access a deferred field, Django fires a synchronous query to fetch it. This causes a silent N+1.
*Always test `.only()` queries with `django-assert-num-queries`.*

## 13. Production Checklist
- [ ] All API endpoints have `select_related`/`prefetch_related` applied.
- [ ] Database query count is strictly asserted in CI using `assertNumQueries`.
- [ ] `only()` is heavily scrutinized for deferred attribute access.
