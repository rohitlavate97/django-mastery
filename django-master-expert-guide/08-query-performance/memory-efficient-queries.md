# Django Mastery: Memory Efficient Queries

## 1. The Memory Cost of Django Instances

A row in PostgreSQL might be 100 bytes. A Django Model instance representing that row is a complex Python object with state, `__dict__`, signal handlers, and related managers. It can easily consume 2-5 KB of RAM.

Fetching 1,000,000 rows into a Django QuerySet:
- PostgreSQL payload: ~100 MB
- Python Memory: ~2-5 GB (OOM Killer triggers 💥)

---

## 2. Server-Side Cursors: `QuerySet.iterator()`

By default, Django fetches all rows from psycopg2 into memory, then builds all Python objects, then returns the QuerySet.

`iterator(chunk_size=N)` uses PostgreSQL server-side cursors (`DECLARE CURSOR`). It fetches rows over the network in chunks, preventing Python memory bloat.

### Basic Implementation
```python
import gc

def process_all_users():
    # 💥 BAD: Loads all millions of users into memory at once
    # for user in User.objects.all():
    #     send_email(user)

    # 🚀 GOOD: Server-side cursor, fetches 2000 at a time
    users = User.objects.iterator(chunk_size=2000)
    
    for user in users:
        send_email(user)
        # Optional: manually clear references if objects are heavy
    
    gc.collect()
```

🔴 **Anti-Pattern:** Using `iterator()` with `prefetch_related`.
If you do `.prefetch_related(\'books\').iterator()`, Django *will* still fetch all related objects into memory for the current chunk. It works, but chunk size heavily dictates memory usage.

---

## 3. Batch Processing Patterns

### OFFSET / LIMIT (The Bad Way)
Paginator uses `OFFSET/LIMIT`. As offset grows, the database must read and discard rows. `OFFSET 1000000 LIMIT 10` is incredibly slow.

### Keyset Pagination (The Good Way)
Also known as "cursor pagination" or "seek method".

```python
def process_in_batches_keyset(batch_size=1000):
    last_id = 0
    while True:
        # Uses standard B-Tree index on primary key
        batch = list(User.objects.filter(id__gt=last_id).order_by(\'id\')[:batch_size])
        
        if not batch:
            break
            
        for user in batch:
            process(user)
            
        last_id = batch[-1].id
```

---

## 4. Bulk Operations

Never loop and `save()`. Always use bulk operations to minimize network RTT and transaction overhead.

### bulk_create
```python
def import_products(data_list):
    products = [
        Product(sku=data[\'sku\'], price=data[\'price\'])
        for data in data_list
    ]
    
    # ignore_conflicts=True acts as ON CONFLICT DO NOTHING (Postgres)
    # update_conflicts=True acts as ON CONFLICT DO UPDATE (Django 4.1+)
    Product.objects.bulk_create(
        products, 
        batch_size=1000,
        update_conflicts=True,
        unique_fields=[\'sku\'],
        update_fields=[\'price\']
    )
```

### bulk_update
```python
def apply_discount(category_id):
    products = list(Product.objects.filter(category_id=category_id))
    for p in products:
        p.price *= 0.90
    
    # Updates ONLY the price field in batches of 1000
    Product.objects.bulk_update(products, fields=[\'price\'], batch_size=1000)
```

### in_bulk
Fetches objects by a list of IDs and returns a dictionary mapped by ID. Extremely fast and avoids N+1 when you have a list of IDs.
```python
# user_ids = [1, 5, 12, 99]
users_dict = User.objects.in_bulk(user_ids)
# users_dict[5] -> User object
```

---

## 5. Streaming Large Datasets to HTTP Clients

If you need to export a 1GB CSV, you cannot build it in RAM. Use `StreamingHttpResponse`.

```python
import csv
from django.http import StreamingHttpResponse

class Echo:
    """An object that implements just the write method of the file-like interface."""
    def write(self, value):
        return value

def export_users_csv(request):
    def generate():
        pseudo_buffer = Echo()
        writer = csv.writer(pseudo_buffer)
        yield writer.writerow([\'ID\', \'Email\', \'Joined\'])
        
        for user in User.objects.iterator(chunk_size=2000):
            # Yields string bytes directly to WSGI/ASGI server
            yield writer.writerow([user.id, user.email, user.date_joined])

    response = StreamingHttpResponse(generate(), content_type="text/csv")
    response[\'Content-Disposition\'] = \'attachment; filename="users.csv"\'
    return response
```

## 6. Environment-Specific Behavior

| Environment | Memory Limit | Behavior on OOM |
|-------------|--------------|-----------------|
| Local (runserver) | None (OS limit) | Laptop freezes, swaps to disk. |
| Docker | Configured via `--memory` | Container instantly Killed (Exit Code 137). |
| Gunicorn/Prod | Worker limit | Gunicorn master kills worker via SIGKILL. User gets 502 Bad Gateway. |

## 7. Production Checklist
- [ ] Large cron jobs / management commands use `iterator()` or keyset pagination.
- [ ] No `for obj in qs: obj.save()` exists in the codebase.
- [ ] CSV/Excel exports use `StreamingHttpResponse`.
- [ ] `bulk_create` uses `batch_size` to prevent single massive SQL strings from exceeding Postgres `max_allowed_packet` limits.
