# The Event Loop in Django ASGI

## 1. Mental Model
```text
The Event Loop (The Conductor):
"Request A is waiting for the DB, I'll pause it."
"Request B is waiting for the Network, I'll pause it."
"DB replied for Request A! I'll resume Request A."

Tasks: [Paused: B], [Running: A], [Pending: C]
```

## 2. Why It Exists
Concurrency via threading/multiprocessing has high overhead (memory per thread, OS context switching CPU cost). The asyncio event loop provides cooperative multitasking within a *single thread*. It achieves massive concurrency by switching tasks precisely when they are waiting for I/O.

## 3. Internal Working
ASGI servers (Uvicorn, Daphne) start an `asyncio` event loop. When a new HTTP request arrives, the server creates an `asyncio.Task` to run Django's ASGI application callable. 
Whenever your code hits an `await` (e.g., `await httpx.get(...)`), control is yielded back to the event loop. The loop uses non-blocking sockets (via `epoll` or `kqueue`) to monitor I/O operations and resumes the task when the data is ready.

## 4. Basic Implementation
```python
# Demonstrating how the loop handles concurrency in Django
import asyncio
from django.http import JsonResponse

async def worker(task_id, delay):
    print(f"Task {task_id} starting...")
    await asyncio.sleep(delay) # Yields to event loop
    print(f"Task {task_id} done!")
    return task_id

async def parallel_view(request):
    # The event loop will run these concurrently
    results = await asyncio.gather(
        worker(1, 2),
        worker(2, 2),
        worker(3, 2)
    )
    # Total time is ~2 seconds, not 6 seconds.
    return JsonResponse({'completed': results})
```

## 5. Production-Ready Implementation
Detecting blocking calls in production is critical. Use `asyncio` debug mode or profiling tools.
```python
# myproject/asgi.py
import os
import asyncio
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

# Enable asyncio debug mode in non-production environments
if os.environ.get('DJANGO_ENV') != 'production':
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    # This will log warnings if a task blocks the loop for > 100ms
    loop.slow_callback_duration = 0.1 

application = get_asgi_application()
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:** CPU-bound processing in the event loop.
```python
async def image_processing_view(request):
    # BAD: This completely stops the event loop for 5 seconds.
    # NO other users can connect or get responses during this time.
    process_image_matrix_sync() 
    
    # GOOD: Run in a separate thread/process
    await sync_to_async(process_image_matrix_sync)()
```

## 7. Environment-Specific Behavior
| OS | Event Loop Implementation | Performance |
|----|---------------------------|-------------|
| Linux | `epoll` via `uvloop` (optional) | Blazing fast |
| macOS | `kqueue` | Excellent |
| Windows| `ProactorEventLoop` | Good for dev, poor for prod |

## 8. Local Development Issues
🔴 SYMPTOM: `RuntimeWarning: coroutine 'X' was never awaited`
🔍 CAUSE: You called an async function but forgot the `await` keyword. The event loop never scheduled it.
🔧 FIX: Always `await` coroutines, or schedule them with `asyncio.create_task()`.

## 9. Production Issues
🚨 INCIDENT: 100% CPU on single core, 0 throughput.
- **Investigation:** Enabled `uvloop` profiling and found a regular expression catastrophic backtracking issue inside an `async def` view. Because the regex was purely CPU-bound, it froze the event loop indefinitely.
- **Fix:** Fix the regex, and move heavy string processing to Celery.

## 10. Failure Simulation
Add `time.sleep(5)` (NOT `asyncio.sleep`) in an async view. Fire 5 concurrent requests using `curl`. Note that they finish sequentially, taking 25 seconds total, proving the loop was blocked.

## 11. Decision Matrix
- **`uvloop`**: Drop-in replacement for standard asyncio loop. Written in Cython on top of libuv (Node.js engine). Use it in production via Uvicorn (`uvicorn --loop uvloop`).

## 12. Senior-Level Questions
**Q:** If I create a background task using `asyncio.create_task()` in an async view, will it continue running after the HTTP response is sent?
**A:** Yes, BUT if the ASGI server restarts or the worker is killed, the task is lost. For durable background jobs, use Celery. For quick, non-critical fire-and-forget (like sending a metric), `create_task()` is fine.

## 13. Production Checklist
- [ ] `uvloop` enabled in Uvicorn/Gunicorn.
- [ ] No blocking I/O (e.g., `urllib`, `requests`) in async paths.
- [ ] Event loop debug mode enabled during staging/load testing to catch slow callbacks.
