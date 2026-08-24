# Middleware Deep Dive [DJANGO 6.1+]

## 1. Mental Model
```text
Middleware Onion Architecture

[Request IN]
   |
   v
( SecurityMiddleware.process_request )
   |
   v
( SessionMiddleware.process_request )
   |
   v
[ ------- VIEW EXECUTION ------- ]
   |
   v
( SessionMiddleware.process_response )
   |
   v
( SecurityMiddleware.process_response )
   |
   v
[Response OUT]
```

## 2. Why It Exists
Provides a hook into Django's request/response lifecycle globally. Perfect for cross-cutting concerns (authentication, logging, CORS, security headers) without polluting view logic.

## 3. Internal Working
Django uses a recursive function (`_get_response` wrapped by each middleware) constructed at server startup in `BaseHandler.load_middleware()`.

Trace of `django/core/handlers/base.py`:
```python
    def load_middleware(self, is_async=False):
        handler = self._get_response
        for middleware_path in reversed(settings.MIDDLEWARE):
            middleware = import_string(middleware_path)
            middleware_can_sync = getattr(middleware, "sync_capable", True)
            middleware_can_async = getattr(middleware, "async_capable", False)
            
            # Wrap the current handler
            handler = middleware(handler)
            
        self._middleware_chain = handler
```
This means `settings.MIDDLEWARE` is applied strictly **Top-Down** for Requests and **Bottom-Up** for Responses.

## 4. Basic Implementation
```python
class SimpleLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        print(f"Incoming: {request.path}")
        response = self.get_response(request)
        print(f"Outgoing: {response.status_code}")
        return response
```

## 5. Production-Ready Implementation
```python
import time
import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)

class RequestLatencyMiddleware:
    sync_capable = True
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.monotonic()
        
        response = self.get_response(request)
        
        duration = time.monotonic() - start_time
        logger.info(
            "request_latency",
            extra={
                "path": request.path,
                "method": request.method,
                "status": response.status_code,
                "latency_ms": round(duration * 1000, 2),
            }
        )
        # Add server-timing header for debugging
        response["Server-Timing"] = f"total;dur={round(duration * 1000, 2)}"
        return response
```

## 6. Anti-Patterns
🔴 **TICKING TIME BOMB**: Mutating request payload directly or querying DB on every request.
```python
class BadAuthMiddleware:
    def __call__(self, request):
        # BAD: DB query on EVERY request (even static files if routed through Django)
        user = User.objects.get(session_id=request.COOKIES['session'])
        request.user = user
        return self.get_response(request)
```

## 7. Environment-Specific Behavior
| Environment | Async Support | Behavior |
|-------------|---------------|----------|
| WSGI | Sync only | Async middleware runs in a synchronous thread pool wrapper. |
| ASGI | Both | Runs native async. Mix of sync/async middleware causes thread context switching overhead. |

## 8. Local Development Issues
🔴 SYMPTOM: `ValueError: <Middleware> is synchronous only, but used with an async handler.`
🔍 CAUSE: You have an async view, but a middleware is not `async_capable`.
🔧 FIX: Add `async_capable = True` if the middleware doesn't do blocking IO, or use `asgiref.sync.iscoroutinefunction` to handle both.

## 9. Production Issues
INCIDENT: Session data corruption / Leakage.
SEVERITY: Critical
CAUSE: `SessionMiddleware` placed BEFORE `UpdateCacheMiddleware`. A cached response was returned with another user's session cookie.
FIX: Enforce correct ordering: `UpdateCacheMiddleware` MUST be first, `SessionMiddleware` AFTER it, `FetchFromCacheMiddleware` LAST.

## 10. Failure Simulation
Test middleware ordering side-effects:
```python
from django.test import RequestFactory
from myapp.middleware import RequestLatencyMiddleware
from django.http import HttpResponse

def test_middleware_adds_header():
    rf = RequestFactory()
    request = rf.get('/test/')
    
    def mock_get_response(req):
        return HttpResponse("ok")
        
    middleware = RequestLatencyMiddleware(mock_get_response)
    response = middleware(request)
    
    assert "Server-Timing" in response.headers
```

## 11. Decision Matrix
| Need | Use Middleware? | Alternative |
|------|-----------------|-------------|
| Add headers to all API responses | ✅ Yes | N/A |
| Rate limiting specific views | ❌ No | View Decorator |
| Extract JWT token globally | ✅ Yes | N/A |

## 12. Senior-Level Questions
**Q: How do you bypass a specific middleware for a specific view?**
A: You cannot natively bypass middleware because they run *before* URL resolution in the onion layer (for global request middleware). However, you can check `request.path.startswith('/api/no-auth/')` inside the middleware and return early.

## 13. Production Checklist
- [ ] Middleware order strictly reviewed.
- [ ] No N+1 DB queries in custom middleware.
- [ ] Both `sync_capable` and `async_capable` declared correctly.
