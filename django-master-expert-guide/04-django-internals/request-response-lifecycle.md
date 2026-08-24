# Request-Response Lifecycle

## 1. Mental Model
```text
Client -> Gunicorn/Uvicorn -> WSGI/ASGI -> Django
                                             |
                                     WSGIHandler.__call__
                                             |
                                   Middleware (Request)
                                             |
                                      URL Resolver
                                             |
                                          View
                                             |
                                   Middleware (Response)
                                             |
Client <- HTTP Response <- WSGI/ASGI <- Django
```

## 2. Why It Exists
The request-response lifecycle maps an incoming HTTP byte stream to a Python dictionary, routes it to the appropriate business logic (View), and returns a formatted HTTP response.

## 3. Internal Working
1. **TCP Connection**: Worker accepts connection.
2. **WSGI environ dict**: Created by the server.
3. **WSGIHandler.__call__**: Entry point in Django.
4. **Middleware (process_request)**: Top-down execution.
5. **URL Resolution**: `URLResolver.resolve(path)`.
6. **View execution**: `request` passed to view.
7. **Middleware (process_response)**: Bottom-up execution.
8. **Response returned**.

## 4. Basic Implementation
```python
# simple view
from django.http import HttpResponse

def my_view(request):
    return HttpResponse("Hello World")
```

## 5. Production-Ready Implementation
```python
from django.http import JsonResponse
from django.views.decorators.http import require_GET
import logging

logger = logging.getLogger(__name__)

@require_GET
def health_check(request):
    try:
        # Check DB or Cache here safely
        return JsonResponse({"status": "healthy"})
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return JsonResponse({"status": "unhealthy"}, status=503)
```

## 6. Anti-Patterns
🔴 **TICKING TIME BOMB**: Blocking ASGI loop.
```python
# INCORRECT in ASGI context
async def my_view(request):
    import time
    time.sleep(5)  # Blocks the entire event loop!
    return HttpResponse("Done")
```

## 7. Environment-Specific Behavior
| Environment | WSGI vs ASGI |
|-------------|--------------|
| WSGI | Synchronous, thread-based or process-based. |
| ASGI | Asynchronous, event-loop based. Handles WebSockets natively. |

## 8. Local Development Issues
🔴 SYMPTOM: `AttributeError: 'WSGIRequest' object has no attribute 'user'`
🔍 CAUSE: `AuthenticationMiddleware` is missing from `MIDDLEWARE` in settings.
🔧 FIX: Add `django.contrib.auth.middleware.AuthenticationMiddleware`.

## 9. Production Issues
INCIDENT: Intermittent 502 Bad Gateway.
SEVERITY: Critical
CAUSE: View is taking too long (>30s), Gunicorn worker times out and is killed by the master process.
FIX: Move long-running tasks to Celery. Return 202 Accepted immediately.

## 10. Failure Simulation
Intentionally break URL resolution:
```python
# urls.py
urlpatterns = [
    # Missing trailing slash can cause 404s if APPEND_SLASH is False
    path('api/data', my_view),
]
```

## 11. Decision Matrix
| Use Case | WSGI | ASGI |
|----------|------|------|
| Standard CRUD DB app | ✅ | ❌ (Overkill) |
| WebSockets / Chat | ❌ | ✅ |

## 12. Senior-Level Questions
**Q: How does Django handle exceptions in a View?**
A: `convert_exception_to_response` catches the exception. It then runs `process_exception` middleware. If unhandled, it falls back to the `handler500` view (which renders the technical 500 page in DEBUG, or a standard 500 page in prod).

## 13. Production Checklist
- [ ] Gunicorn timeout properly configured.
- [ ] `APPEND_SLASH` behavior understood.
- [ ] `SECURE_PROXY_SSL_HEADER` configured if behind a reverse proxy.
