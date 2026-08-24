# Common PR Issues in Django: The Silent Killers

## Mental Model
Automated tools (linters, type checkers, basic CI tests) catch syntax errors, PEP8 violations, and simple regressions. They DO NOT catch architectural flaws, concurrency issues, or database performance bottlenecks that only manifest under production load.

```text
[ Local Environment ] ---> [ CI Pipeline ] ---> [ Code Review ] ---> [ Production ]
  Data Volume: Low           Data Volume: Low     Focus: Architecture  Data Volume: Massive
  Concurrency: 1             Concurrency: 1                            Concurrency: High
  Latency: 0ms               Latency: 0ms                              Latency: Variable
```

## 1. The Implicit N+1 Query in Serializers

🔴 **SYMPTOM:** High CPU usage on the database, slow API response times.
🔍 **CAUSE:** DRF serializers accessing related fields without `prefetch_related` in the view.

```python
# ❌ Anti-pattern: Looks fine in PR, explodes in production
class AuthorSerializer(serializers.ModelSerializer):
    books_count = serializers.SerializerMethodField()

    class Meta:
        model = Author
        fields = ['name', 'books_count']

    def get_books_count(self, obj):
        return obj.books.count() # N+1 query if `books` isn't prefetched

# ✅ Production Implementation
# In ViewSet:
queryset = Author.objects.annotate(books_count=Count('books'))

class AuthorSerializer(serializers.ModelSerializer):
    books_count = serializers.IntegerField(read_only=True) # Reads annotated value
```

## 2. Using `len()` on a QuerySet instead of `.count()`

🔴 **SYMPTOM:** High memory usage, slow execution.
🔍 **CAUSE:** Calling `len()` on a QuerySet evaluates the entire query, pulling all records into Python memory.

```python
# ❌ Anti-pattern
active_users = User.objects.filter(is_active=True)
if len(active_users) > 1000: # Fetches all users into memory!
    pass

# ✅ Production Implementation
if User.objects.filter(is_active=True).count() > 1000: # SELECT COUNT(*)
    pass
```

## 3. Unbounded Queries

🔴 **SYMPTOM:** OOM (Out of Memory) kills, database timeouts.
🔍 **CAUSE:** Fetching all records without pagination or limits.

```python
# ❌ Anti-pattern
def export_users():
    for user in User.objects.all(): # Fetches millions of rows at once
        process(user)

# ✅ Production Implementation
def export_users():
    for user in User.objects.iterator(chunk_size=2000): # Server-side cursors
        process(user)
```

## 4. Race Conditions in Read-Modify-Write Cycles

🔴 **SYMPTOM:** Lost updates, inconsistent balances, double processing.
🔍 **CAUSE:** Reading a value, modifying it in Python, and saving it back without locking.

```python
# ❌ Anti-pattern
def apply_discount(product_id):
    product = Product.objects.get(id=product_id)
    if product.stock > 0:
        product.stock -= 1
        product.save()

# ✅ Production Implementation
from django.db import transaction

def apply_discount(product_id):
    with transaction.atomic():
        # Locks the row until transaction ends
        product = Product.objects.select_for_update().get(id=product_id)
        if product.stock > 0:
            product.stock -= 1
            product.save()
```

## 5. Missing Database Indexes on Filtered Fields

🔴 **SYMPTOM:** Sequential scans on large tables, query latency increases linearly with table size.
🔍 **CAUSE:** Filtering by fields that are not indexed.

```python
# ❌ Anti-pattern
class Order(models.Model):
    status = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

# ✅ Production Implementation
class Order(models.Model):
    status = models.CharField(max_length=20, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'created_at']), # Composite index for complex queries
        ]
```

## 6. Calling External APIs in the Request-Response Cycle

🔴 **SYMPTOM:** API endpoints hang, workers tie up, site goes down.
🔍 **CAUSE:** Synchronous external network calls in a Django view.

```python
# ❌ Anti-pattern
def signup(request):
    user = User.objects.create(...)
    requests.post('https://email-service.com/send', data={'to': user.email}) # Blocks response!
    return Response({'status': 'success'})

# ✅ Production Implementation
def signup(request):
    user = User.objects.create(...)
    send_welcome_email_task.delay(user.id) # Async Celery task
    return Response({'status': 'success'})
```

## 7. Using `default=dict` or `default=list` in JSONFields

🔴 **SYMPTOM:** Data leaks between rows, unexpected defaults.
🔍 **CAUSE:** Mutable default arguments in models evaluate once when the class is loaded.

```python
# ❌ Anti-pattern
class Profile(models.Model):
    preferences = models.JSONField(default={}) # Shared across all instances!

# ✅ Production Implementation
class Profile(models.Model):
    preferences = models.JSONField(default=dict) # Callable!
```

## 8. Missing Timeouts on `requests`

🔴 **SYMPTOM:** Celery queues fill up, web workers hang forever.
🔍 **CAUSE:** `requests.get()` blocks indefinitely if the server accepts the connection but never responds.

```python
# ❌ Anti-pattern
response = requests.get('https://api.thirdparty.com/data')

# ✅ Production Implementation
response = requests.get('https://api.thirdparty.com/data', timeout=(3.0, 10.0)) # (connect, read) timeouts
```
