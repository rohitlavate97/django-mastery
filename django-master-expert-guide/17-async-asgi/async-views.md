# Async Views and ORM in Django

## 1. Mental Model
```text
Async View:
async def my_view(request):
    data = await httpx.get(...)  # Yields loop to other requests
    user = await User.objects.aget(id=1) # Async DB access
    return JsonResponse({...})
```

## 2. Why It Exists
Standard sync views tie up a worker thread for the entire duration of the request. If the request spends 99% of its time waiting for a third-party API or a slow database query, that thread is wasted. Async views allow the worker to handle other incoming requests during that wait time, drastically increasing throughput.

## 3. Internal Working
When Django routes a request to an `async def` view under an ASGI server, it executes the view as an asyncio task. For ORM operations, Django provides async wrappers (`aget`, `acreate`, `afirst`) which internally use `sync_to_async` to run the actual synchronous psycopg2/psycopg3 operations in a thread pool (though Django 4.2+ with psycopg3 has native async support for Postgres!).

## 4. Basic Implementation
```python
import httpx
from django.http import JsonResponse
from myapp.models import Article

async def async_dashboard(request):
    # Async HTTP call
    async with httpx.AsyncClient() as client:
        response = await client.get('https://api.example.com/data')
    
    # Async ORM call
    articles = [a async for a in Article.objects.filter(published=True)]
    
    return JsonResponse({
        'api_data': response.json(),
        'articles': [a.title for a in articles]
    })
```

## 5. Production-Ready Implementation
```python
import asyncio
import httpx
from django.http import JsonResponse
from .models import ServiceStatus

async def fan_out_view(request):
    urls = ['http://api1.com', 'http://api2.com', 'http://api3.com']
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        # Run requests concurrently
        tasks = [client.get(url) for url in urls]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
    results = []
    for resp in responses:
        if isinstance(resp, Exception):
            results.append({'error': str(resp)})
        else:
            results.append(resp.json())
            
    # Async bulk create
    await ServiceStatus.objects.abulk_create([
        ServiceStatus(log=str(res)) for res in results
    ])
    
    return JsonResponse({'status': 'ok', 'data': results})
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:** Iterating over a queryset synchronously inside an async view.
```python
# BAD: Blocks event loop!
async def view(request):
    users = list(User.objects.all()) # Synchronous execution

# GOOD:
async def view(request):
    users = [u async for u in User.objects.all()]
```

## 7. Environment-Specific Behavior
| DB Engine | Native Async ORM Support | Behavior |
|-----------|--------------------------|----------|
| PostgreSQL (psycopg3) | Yes (Django 4.2+) | True async, no thread pool overhead |
| PostgreSQL (psycopg2) | No | Uses `sync_to_async` thread pool |
| SQLite/MySQL | No | Uses `sync_to_async` thread pool |

## 8. Local Development Issues
🔴 SYMPTOM: `SynchronousOnlyOperation` exception raised.
🔍 CAUSE: You tried to evaluate a queryset (e.g., calling `.count()`, iterating, accessing a lazy related field) without `await` or async iterators.
🔧 FIX: Use `.acount()`, `async for`, or `await obj.arefresh_from_db()`.

## 9. Production Issues
🚨 INCIDENT: High latency on async endpoints under load.
- **Investigation:** Developers were using `requests.get()` instead of `httpx.AsyncClient()`. `requests` is strictly synchronous and blocks the event loop.
- **Fix:** Lint codebase for synchronous network/file I/O in `async def` views.

## 10. Failure Simulation
Try accessing a related ForeignKey field (that wasn't `select_related`) inside an async view: `print(user.profile.name)`. It will crash with `SynchronousOnlyOperation`. Fix it by using `await user.profile.aget()`.

## 11. Decision Matrix
- **Use Async Views:** Web scraping, aggregating data from multiple APIs, heavy chat/SSE endpoints.
- **Avoid Async Views:** CPU-bound tasks (image processing, heavy cryptography). Use Celery instead.

## 12. Senior-Level Questions
**Q:** Does converting all my Django views to `async def` make my app faster?
**A:** NO. If your views just do standard CRUD against a database using the thread-pool fallback, async views might actually be *slower* due to context-switching overhead. Async only helps if you have significant concurrent I/O waits.

## 13. Production Checklist
- [ ] Psycopg3 installed for native PostgreSQL async.
- [ ] All HTTP clients migrated to async (`httpx` or `aiohttp`).
- [ ] No synchronous ORM evaluations in async paths.
