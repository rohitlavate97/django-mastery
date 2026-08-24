# Sync-Async Boundary in Django

## 1. Mental Model
```text
Event Loop (Async World) <=========> Thread Pool (Sync World)
         |                                  |
     async def view                   def legacy_function()
         |                                  |
 await sync_to_async(legacy)() ----> executes in thread
         |                                  |
async_to_sync(async_func)() <------- waits for event loop task
```

## 2. Why It Exists
Django is over 15 years old, and its ecosystem (middleware, auth, admin, third-party packages) is overwhelmingly synchronous. We cannot rewrite the entire framework and ecosystem overnight. The sync-async boundary allows seamless context switching between synchronous and asynchronous code.

## 3. Internal Working
- **`sync_to_async`**: Takes a synchronous callable and returns an asynchronous coroutine. Internally, it submits the synchronous function to an `asgiref.sync.SyncToAsync` thread pool executor. The event loop awaits the future returned by the executor.
- **`async_to_sync`**: Takes an asynchronous coroutine and makes it callable synchronously. Internally, it creates a new event loop (or uses the existing one in a different thread) and runs the coroutine until complete using `loop.run_until_complete()`.

## 4. Basic Implementation
```python
from asgiref.sync import sync_to_async, async_to_sync
import requests
import httpx

# 1. Sync function in an Async View
def slow_sync_math(x):
    return sum(i * i for i in range(x))

async def my_async_view(request):
    # Offload blocking CPU work to a thread
    result = await sync_to_async(slow_sync_math)(10000000)
    return JsonResponse({'res': result})

# 2. Async function in a Sync View
async def fetch_data():
    async with httpx.AsyncClient() as client:
        return await client.get('http://api.com')

def my_sync_view(request):
    # Run async code safely in a sync view
    result = async_to_sync(fetch_data)()
    return HttpResponse(result.content)
```

## 5. Production-Ready Implementation
```python
from asgiref.sync import sync_to_async

# Configuring thread-sensitivity
# thread_sensitive=True (default) ensures operations run in the same thread
# as the main request, which is CRITICAL for SQLite and some older thread-local states.
# thread_sensitive=False allows the executor to run it in any thread pool worker.

@sync_to_async(thread_sensitive=False)
def heavy_file_io(filepath):
    with open(filepath, 'r') as f:
        return f.read()

async def read_logs_view(request):
    content = await heavy_file_io('/var/log/app.log')
    return HttpResponse(content)
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:** Nesting `async_to_sync` inside `sync_to_async` or vice-versa too deeply. This can lead to thread exhaustion and deadlocks because each boundary crossing allocates resources waiting for the other side.
🔴 **Ticking Time Bomb:** Using `thread_sensitive=False` with Django's ORM operations or anything relying on thread-local variables (like `django.utils.translation` or `current_request` middlewares).

## 7. Environment-Specific Behavior
| Context | `thread_sensitive=True` | `thread_sensitive=False` |
|---------|-------------------------|--------------------------|
| Default ThreadPool | Django uses a specialized executor ensuring same-thread execution. | Standard ThreadPoolExecutor |
| Performance | Slower, blocks main sync thread pool. | Faster, truly parallel, but risky for DBs. |

## 8. Local Development Issues
🔴 SYMPTOM: `RuntimeError: You cannot use AsyncToSync in the same thread as an async event loop`
🔍 CAUSE: You called `async_to_sync` directly inside an `async def` function (or a sync function that was wrapped with `sync_to_async` with `thread_sensitive=True`).
🔧 FIX: Don't use `async_to_sync`. Just `await` the async function directly.

## 9. Production Issues
🚨 INCIDENT: Server Deadlock
- **Investigation:** A complex middleware chain mixed sync and async middlewares. A sync middleware called an async view, which internally triggered a sync ORM signal, which triggered an async cache set. The thread pool ran out of workers.
- **Fix:** Align middleware stack. If using async views, try to use async-compatible middlewares. Avoid deeply nested boundary crossings.

## 10. Failure Simulation
Create a circular boundary call: an async view calls a sync function via `sync_to_async`, which in turn calls an async function via `async_to_sync`. Watch the request deadlock and time out.

## 11. Decision Matrix
- **`sync_to_async`**: Use when you are inside an `async def` view and MUST call legacy sync code (like `requests`, `boto3`, or complex XML parsing).
- **`async_to_sync`**: Use when you are in a Django management command, Celery task, or legacy sync view and MUST call a modern async library.

## 12. Senior-Level Questions
**Q:** What is the performance penalty of `sync_to_async`?
**A:** It involves thread context switching, acquiring locks, and passing futures between the loop and the executor. For a very fast function (< 1ms), the overhead of context switching might take longer than the function itself!

## 13. Production Checklist
- [ ] Minimize boundary crossings in the hot path.
- [ ] Ensure `thread_sensitive=True` is used for ORM interactions.
- [ ] Monitor thread pool usage if heavy on `sync_to_async`.
