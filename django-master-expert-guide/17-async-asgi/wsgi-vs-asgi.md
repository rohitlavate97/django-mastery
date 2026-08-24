# WSGI vs ASGI in Django

## 1. Mental Model
```text
WSGI (Sync):
Request 1 -> Worker Thread -> Block on DB -> DB Returns -> Response
Request 2 -> Worker Thread -> Block on API -> API Returns -> Response
(Requires many threads/processes to handle high concurrency)

ASGI (Async):
Request 1 -> Event Loop -> Await DB (Yield control)
Request 2 -> Event Loop -> Await API (Yield control)
Event Loop -> DB Returns -> Resume Request 1 -> Response
(Single thread handles thousands of connections efficiently)
```

## 2. Why It Exists
WSGI (Web Server Gateway Interface) was designed in the early 2000s for synchronous Python. As real-time web features (WebSockets, SSE, long-polling) and high-concurrency microservices emerged, the thread-per-connection model became a massive memory and CPU bottleneck. ASGI (Asynchronous Server Gateway Interface) standardizes async Python web apps, allowing an event loop to handle massive concurrent I/O.

## 3. Internal Working
In WSGI, `application(environ, start_response)` is called. It blocks until completion.
In ASGI, `async def application(scope, receive, send)` is called.
- `scope`: Dict containing connection details (headers, path).
- `receive`: Async callable to get incoming messages (e.g., request body chunks, websocket frames).
- `send`: Async callable to send outgoing messages.

Django's ASGI handler intercepts the scope. If it's an HTTP scope, it resolves the route. If the view is `async def`, it executes it directly in the event loop. If it's `def` (sync), it wraps it in `sync_to_async` and runs it in a thread pool.

## 4. Basic Implementation
**asgi.py**
```python
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

application = get_asgi_application()
```
Run with Uvicorn: `uvicorn myproject.asgi:application --workers 4`

## 5. Production-Ready Implementation
Use Gunicorn as a process manager with Uvicorn workers for resilience and performance.
```bash
gunicorn myproject.asgi:application -k uvicorn.workers.UvicornWorker -w 4 --max-requests 1000 --max-requests-jitter 50
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:** Running blocking I/O (like `requests.get` or a heavy math computation) inside an `async def` view without using a thread pool. This freezes the entire event loop, completely halting the server.

## 7. Environment-Specific Behavior
| Server | Features | Best For |
|--------|----------|----------|
| Uvicorn| Fast, mature | Standard HTTP/WebSockets |
| Daphne | Django channels | Channels integration |
| Granian| Rust-based, ultra-fast | High performance prod |

## 8. Local Development Issues
🔴 SYMPTOM: Server locks up entirely on one request.
🔍 CAUSE: You called a synchronous blocking function (e.g., `time.sleep()`) in an async view.
🔧 FIX: Use `await asyncio.sleep()` or wrap the sync function with `sync_to_async`.

## 9. Production Issues
🚨 INCIDENT: Slow response times across all endpoints during traffic spikes.
- **Investigation:** One endpoint was doing heavy JSON processing synchronously inside the event loop.
- **Fix:** Offload CPU-bound work to Celery or run it in a `ProcessPoolExecutor`.

## 10. Failure Simulation
Create an `async def` view with `import time; time.sleep(10)`. Open two browser tabs to this endpoint. The second tab will hang until the first finishes. Change to `await asyncio.sleep(10)` and both will finish simultaneously.

## 11. Decision Matrix
- **Stick to WSGI if:** Your app is purely CRUD, uses legacy synchronous libraries, and doesn't need WebSockets.
- **Migrate to ASGI if:** You need high concurrency, WebSockets, SSE, or are orchestrating many slow external API calls.

## 12. Senior-Level Questions
**Q:** Why does Django create a thread pool even in ASGI mode?
**A:** Because many parts of Django (and existing apps) are still synchronous. To prevent sync code from blocking the async event loop, Django executes sync middleware and sync views in a thread pool via `sync_to_async`.

## 13. Production Checklist
- [ ] ASGI server deployed (Uvicorn/Daphne/Granian).
- [ ] Gunicorn used as process manager.
- [ ] `ASGI_THREADS` configured if heavily relying on sync views.
- [ ] Codebase audited for blocking calls in async contexts.
