# Django Mastery: The N+1 Query Problem

## 1. Mental Model: The Lazy Evaluation Trap

The N+1 problem occurs when an application makes one database query to fetch a list of N items, and then makes N additional queries to fetch related data for each item.

```text
[Mental Model: The N+1 Waterfall]

  Client Request
       │
       ▼
  Query 1: SELECT * FROM author;  (Returns 100 authors)
       │
       ├──► Query 2: SELECT * FROM book WHERE author_id = 1;
       ├──► Query 3: SELECT * FROM book WHERE author_id = 2;
       ├──► ...
       └──► Query 101: SELECT * FROM book WHERE author_id = 100;

Total Queries: 1 + 100 = 101
Total Latency: 101 * Network RTT = 🐢 Unacceptably Slow
```

### Why it Exists: Django ORM\'s Lazy Evaluation
Django\'s ORM evaluates querysets lazily. It only hits the database when you iterate over the queryset, slice it, or force evaluation (e.g., `list()`). 
When you access a related field (Foreign Key, One-to-One, Many-to-Many) on a model instance that hasn\'t been fetched via `select_related` or `prefetch_related`, Django automatically issues a new synchronous query to fetch it.

---

## 2. Taxonomy of N+1 Occurrences

### A. Template Rendering Loops
The most common beginner trap.

**BROKEN (N+1)**
```python
# views.py
def author_list(request):
    authors = Author.objects.all()  # Query 1
    return render(request, \'authors.html\', {\'authors\': authors})

# authors.html
{% for author in authors %}
    <!-- Triggers 1 query per author -->
    <p>{{ author.profile.bio }}</p> 
{% endfor %}
```

**FIXED**
```python
def author_list(request):
    # Query 1: SELECT author.*, profile.* FROM author JOIN profile ...
    authors = Author.objects.select_related(\'profile\').all()
    return render(request, \'authors.html\', {\'authors\': authors})
```

### B. DRF Serializers (The Silent Killer)

#### SerializerMethodField
🔴 **SYMPTOM:** High database load during API responses.
🔍 **CAUSE:** `SerializerMethodField` executes arbitrary Python code per item.

```python
class AuthorSerializer(serializers.ModelSerializer):
    latest_book = serializers.SerializerMethodField()

    class Meta:
        model = Author
        fields = [\'id\', \'name\', \'latest_book\']

    def get_latest_book(self, obj):
        # 💣 TICKING TIME BOMB: 1 query per author
        return obj.books.order_by(\'-published_date\').first().title
```

🔧 **FIX:** Use `Prefetch` with custom querysets in the view.
```python
# views.py
class AuthorViewSet(viewsets.ReadOnlyModelViewSet):
    # Fetch latest book efficiently
    latest_book_qs = Book.objects.order_by(\'-published_date\')
    queryset = Author.objects.prefetch_related(
        Prefetch(\'books\', queryset=latest_book_qs, to_attr=\'_prefetched_latest_book\')
    )

# serializers.py
    def get_latest_book(self, obj):
        books = getattr(obj, \'_prefetched_latest_book\', [])
        return books[0].title if books else None
```

#### Nested Serializers
Nested serializers trigger N+1 if the view queryset doesn\'t prefetch.

```python
class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = [\'title\']

class AuthorSerializer(serializers.ModelSerializer):
    books = BookSerializer(many=True) # Needs prefetch_related(\'books\')
```

### C. Model Properties Calling FKs

```python
class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    
    @property
    def customer_tier(self):
        # 💣 Hidden query if customer wasn\'t select_related
        return self.customer.loyalty_tier 
```

### D. Signals Triggering Lookups
`post_save` signals that fetch related objects without the caller realizing it.

---

## 3. Automated Detection Tools

| Tool | Environment | Description |
|------|-------------|-------------|
| `django-zen-queries` | Test / Local | Fails tests or errors if queries execute where they shouldn\'t (e.g., templates, serializers). |
| `nplusone` | Test / Local | Detects N+1 explicitly and raises exceptions. |
| `django_assert_num_queries` | Test | Pytest fixture to strictly assert exact query counts. |
| `CaptureQueriesContext` | Test | Django\'s built-in context manager for query counting. |

### Pytest Enforcement [PREVENT & EVOLVE]
```python
import pytest
from django.test.utils import CaptureQueriesContext
from django.db import connection

@pytest.mark.django_db
def test_author_api_query_count(api_client, author_factory):
    author_factory.create_batch(10)
    
    with CaptureQueriesContext(connection) as ctx:
        response = api_client.get(\'/api/authors/\')
    
    # Exactly 2 queries expected: 1 for authors, 1 for books prefetch
    assert len(ctx.captured_queries) == 2
```

---

## 4. Production Incident: The Black Friday Outage

### Incident Report [SEV-1]
- **Symptom:** API latency spiked from 120ms to 45,000ms. DB CPU hit 100%. Connections exhausted.
- **Timeline:**
  - 08:00 AM: Black Friday email blast goes out.
  - 08:02 AM: PagerDuty alert: API High Latency.
  - 08:05 AM: Database Max Connections Reached. Site down.
- **Root Cause:** A new "Featured Products" section in the cart dropdown used `SerializerMethodField` to fetch product reviews. Cart items = 5, Reviews per item = 10. `5 * 10 = 50` extra queries per user API hit. With 10,000 concurrent users, the DB received 500,000 queries per second.
- **Fix (Multi-step):**
  1. *Immediate mitigation:* Revert the PR introducing the reviews in the cart.
  2. *Code Fix:* Use `Prefetch(\'reviews\', queryset=Review.objects.only(\'rating\'))`.
  3. *Prevention:* Integrated `nplusone` in CI and strict `assertNumQueries` on all critical API endpoints.

---

## 5. Senior-Level Questions

**Q: When should I use `select_related` vs `prefetch_related`?**
A: `select_related` uses SQL `JOIN` and is for single-valued relationships (Foreign Key, One-to-One). It results in 1 large query. `prefetch_related` does a separate lookup for each relationship and does the "joining" in Python. It is required for multi-valued relationships (Many-to-Many, Reverse Foreign Key), but can also be used for Foreign Keys if the SQL JOIN would create an unmanageably large result set (cartesian explosion).

**Q: Can `prefetch_related` cause memory issues?**
A: Yes. If you prefetch a related set that has millions of rows (e.g., an author with 1,000,000 log entries), Django instantiates 1,000,000 Python objects in memory, killing the worker. Always paginate or limit prefetches using custom `Prefetch` objects.

## 6. Production Checklist
- [ ] `django-debug-toolbar` is active in local dev to visualize queries.
- [ ] Pytest suite uses `django_assert_max_num_queries` for all list API endpoints.
- [ ] DRF ViewSets use `select_related` and `prefetch_related` systematically.
- [ ] Review all `@property` methods on models for hidden database access.
- [ ] CI pipeline fails on N+1 query regression.
