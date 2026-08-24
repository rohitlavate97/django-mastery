# Error Handling Internals [DJANGO 6.1+]

## 1. Mental Model
```text
[View Raises Exception]
          |
          v
  django.core.handlers.exception.convert_exception_to_response()
          |
          v
  [ process_exception Middleware (Bottom-Up) ]
          |
   (If Unhandled)
          v
  [ Default handler500 / handler404 ]
          |
  ( DEBUG=True ? Technical 500 Page : Custom 500 Page )
```

## 2. Why It Exists
Prevents uncaught Python exceptions from dropping TCP connections. Provides centralized logging, customizable error pages, and security (hiding stack traces in production).

## 3. Internal Working
Trace of `django/core/handlers/exception.py`:
```python
def convert_exception_to_response(get_response):
    @wraps(get_response)
    def inner(request):
        try:
            response = get_response(request)
        except Exception as exc:
            response = response_for_exception(request, exc)
        return response
    return inner

def response_for_exception(request, exc):
    if isinstance(exc, Http404):
        # returns handler404
    elif isinstance(exc, PermissionDenied):
        # returns handler403
    elif isinstance(exc, SuspiciousOperation):
        # logs to django.security and returns handler400
    else:
        # Logs as ERROR and returns handler500
        signals.got_request_exception.send(sender=None, request=request)
        response = get_exception_response(request, get_resolver(get_urlconf()), 500, exc)
    return response
```

## 4. Production-Ready Implementation
```python
# urls.py
handler500 = 'my_app.views.custom_error_500'

# views.py
from django.http import JsonResponse

def custom_error_500(request, *args, **kwargs):
    if request.path.startswith('/api/'):
        return JsonResponse({"error": "Internal Server Error"}, status=500)
    
    from django.shortcuts import render
    return render(request, 'errors/500.html', status=500)
```

## 5. Anti-Patterns
🔴 **TICKING TIME BOMB**: Catching generic `Exception` in views without logging or re-raising.
```python
def bad_view(request):
    try:
        data = do_something()
    except Exception: # SILENTLY SWALLOWS ERRORS
        pass
    return HttpResponse("OK")
```

## 6. Environment-Specific Behavior
| Environment | DEBUG | Behavior |
|-------------|-------|----------|
| Local Dev | True | Rich traceback HTML page shown to user. |
| Production | False | Minimal 500 HTML page shown. Error logged to `sys.stderr` / Sentry. |

## 7. Production Checklist
- [ ] `DEBUG=False` in production.
- [ ] `ADMINS` configured so Django sends 500 error emails (or use Sentry).
- [ ] API routes return JSON on 500s, not HTML.
