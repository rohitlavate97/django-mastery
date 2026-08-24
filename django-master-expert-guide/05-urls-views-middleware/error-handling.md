# Error Handling: Flow, Exceptions & Production Monitoring

## 1. Mental Model: The Safety Net

In a production Django application, an unhandled exception is catastrophic. Django provides a robust, multi-layered safety net to catch, process, and convert Python exceptions into appropriate HTTP responses.

```text
View Raises Exception
        |
        v
Django BaseHandler._get_response catches exception
        |
        v
Calls process_exception() on all Middleware
        |
        v
convert_exception_to_response()
        |
   +----+----+
   |         |
Http404   PermissionDenied   Other (500)
   |         |                   |
handler404 handler403       handler500
   |         |                   |
Response  Response          Technical 500 View (if DEBUG) / Server Error View
```

### Why It Exists
We cannot expect every view to wrap its code in a `try/except Exception` block. A centralized error handling mechanism ensures consistent API responses, proper logging, and security (preventing stack traces from leaking to end users).

---

## 2. Django Exception Hierarchy

Django defines several core exceptions that automatically map to HTTP status codes:

1. **`django.http.Http404`**: Maps to 404 Not Found. Raised explicitly or by shortcuts like `get_object_or_404`.
2. **`django.core.exceptions.PermissionDenied`**: Maps to 403 Forbidden. Raised by authentication backends or views.
3. **`django.core.exceptions.SuspiciousOperation`**: Maps to 400 Bad Request. Raised for security issues (e.g., host header manipulation, invalid session cookies).
4. **`django.core.exceptions.ValidationError`**: Used heavily in forms and models. (Note: Does not automatically map to an HTTP status in standard views; must be handled explicitly, though DRF handles it automatically as 400).

---

## 3. Exception Handling Flow: The Guts

When a view crashes, the WSGI/ASGI handler acts as the top-level orchestrator.

### Trace of `BaseHandler.convert_exception_to_response`
```python
# Conceptual trace of django/core/handlers/base.py
def _get_response(self, request):
    try:
        response = wrapped_callback(request, *callback_args, **callback_kwargs)
    except Exception as e:
        response = self.process_exception_by_middleware(e, request)
        if response is None:
            # Fallback to default exception response generator
            response = self.convert_exception_to_response(e, request)
    return response

def convert_exception_to_response(self, e, request):
    if isinstance(e, Http404):
        return get_exception_response(request, self.get_response, 404, e)
    elif isinstance(e, PermissionDenied):
        return get_exception_response(request, self.get_response, 403, e)
    # ... handles others ...
    else:
        # Unexpected 500 error!
        signals.got_request_exception.send(sender=self.__class__, request=request)
        return self.handle_uncaught_exception(request, self.get_response, sys.exc_info())
```

---

## 4. Custom Error Views: JSON APIs vs HTML

By default, Django returns HTML pages for 404/500. For an API, this breaks clients expecting JSON. You must override the default handlers in your root `urls.py`.

### Production Implementation (JSON Error Handlers)

```python
# views.py
from django.http import JsonResponse
import logging

logger = logging.getLogger('django.request')

def custom_error_404(request, exception=None):
    return JsonResponse({
        "error": "Not Found",
        "detail": "The requested resource does not exist.",
        "path": request.path
    }, status=404)

def custom_error_500(request):
    """
    Catch-all for uncaught exceptions.
    IMPORTANT: Do not attempt complex DB queries here. If the DB is down, this will crash too!
    """
    return JsonResponse({
        "error": "Internal Server Error",
        "detail": "An unexpected error occurred. Our team has been notified."
    }, status=500)

# root urls.py
handler404 = 'my_app.views.custom_error_404'
handler500 = 'my_app.views.custom_error_500'
```

---

## 5. Production Error Monitoring: Sentry Integration

Logging to a file is not enough. Tools like Sentry capture tracebacks, local variables, and request context.

### Proper Sentry Setup & PII Scrubbing

You must ensure sensitive data (passwords, auth tokens, credit cards) never reach the error tracking platform.

```python
# settings.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

def before_send(event, hint):
    """Scrub PII before sending to Sentry"""
    if 'request' in event and 'data' in event['request']:
        # Scrub POST body data
        sensitive_keys = ['password', 'secret', 'credit_card', 'ssn']
        for key in sensitive_keys:
            if key in event['request']['data']:
                event['request']['data'][key] = '[FILTERED]'
    return event

sentry_sdk.init(
    dsn="https://examplePublicKey@o0.ingest.sentry.io/0",
    integrations=[DjangoIntegration()],
    traces_sample_rate=0.2, # Don't trace 100% in high-throughput APIs
    send_default_pii=False,
    before_send=before_send
)
```

---

## 6. Anti-Patterns & Ticking Time Bombs

**Anti-Pattern**: Broad except blocks that swallow errors silently.
```python
# BROKEN
def process_payment(request):
    try:
        charge_card()
    except Exception: # Swallows everything, even MemoryError or SyntaxError!
        pass # The worst thing you can do.
    return HttpResponse("OK")
```

**Anti-Pattern**: Returning 200 OK for errors.
```python
# BROKEN (Breaks HTTP semantics and monitoring tools)
def api_view(request):
    try:
        raise ValueError("Bad data")
    except ValueError as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=200) 
```

---

## 7. Runbook: Handling Unexpected 500 Spikes

**INCIDENT**: PagerDuty alerts a sudden spike in 5xx HTTP responses.

**Phase 1: Detection & Triage**
1. Open Sentry/Datadog to identify the exact exception class and traceback.
2. Filter logs by the `X-Correlation-ID` if tied to a specific user report.
3. Determine scope: Is it a single endpoint or application-wide? (e.g., Database connection failure).

**Phase 2: Investigation (Common Causes)**
- **DB Connection Issues**: `OperationalError: FATAL: too many connections`. -> Check connection pooling (PgBouncer).
- **Migration Missing**: `ProgrammingError: relation "app_model" does not exist`. -> Was a deployment rushed without running `migrate`?
- **Third-Party API Outage**: `requests.exceptions.Timeout`. -> Ensure timeouts are set on all external calls.

**Phase 3: Mitigation**
- If deployment caused it: **Rollback immediately**.
- If third-party API: Toggle feature flag to disable the integration temporarily.

## 8. Production Readiness Checklist
- [ ] `DEBUG = False` is enforced in production via environment variables.
- [ ] `ADMINS` setting is configured to email developers on 500s (if Sentry is not used).
- [ ] Custom `handler404` and `handler500` are implemented to match the application's content type (JSON/HTML).
- [ ] Sentry (or similar) is installed with a PII scrubbing `before_send` hook.
- [ ] Database timeouts and external API call timeouts are explicitly configured to prevent stalled requests from causing cascading 500s.
