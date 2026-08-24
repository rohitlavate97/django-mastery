# Request-Response Lifecycle [DJANGO 6.1+]

## 1. Mental Model
```text
[Client] -> [Nginx/ALB] -> [Gunicorn (WSGI)/Uvicorn (ASGI)]
                                |
                                v
                    +-----------------------+
                    |  django.core.servers  |
                    |  WSGIHandler.__call__ |
                    +-----------------------+
                                |
                   [Middleware Onion Entry]
                   1. SecurityMiddleware
                   2. SessionMiddleware
                   3. CommonMiddleware
                   4. CsrfViewMiddleware
                   5. AuthenticationMiddleware
                   6. MessageMiddleware
                                |
                    +-----------------------+
                    |     URL Resolver      |
                    | (Regex Trie Matching) |
                    +-----------------------+
                                |
                    +-----------------------+
                    |         View          |
                    |   (Business Logic)    |
                    +-----------------------+
                                |
                   [Middleware Onion Exit]
                   6. MessageMiddleware
                   ...
                   1. SecurityMiddleware
                                |
                         [HTTP Response]
```

## 2. Why It Exists
The request-response lifecycle maps an incoming HTTP byte stream to a Python dictionary, routes it to the appropriate business logic (View), and returns a formatted HTTP response.

## 3. Internal Working
Trace of `django/core/handlers/base.py`:
```python
# django/core/handlers/base.py - BaseHandler.get_response
class BaseHandler:
    def get_response(self, request):
        set_urlconf(settings.ROOT_URLCONF)
        response = self._middleware_chain(request)
        response._resource_closers.append(request.close)
        if response.status_code >= 400:
            log_response(
                "%s: %s",
                response.reason_phrase,
                request.path,
                response=response,
                request=request,
            )
        return response
```

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
| Environment | WSGI vs ASGI | Behavior |
|-------------|--------------|----------|
| Local | WSGI/ASGI | Sync runserver, auto-reload on. |
| Docker | WSGI/ASGI | Run via gunicorn/uvicorn, explicit worker counts. |
| CI | WSGI | Simple gunicorn setup for testing. |
| Staging | ASGI | Uvicorn + Gunicorn process manager. |
| 100k RPS Prod | ASGI | Multiple Uvicorn workers behind ALB, connection pooling, Redis caching. |

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
