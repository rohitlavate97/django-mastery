# API Design Principles and REST Maturity

## 1. Mental Model: Richardson Maturity Model

```text
Level 0: The Swamp of POX (Plain Old XML/JSON) - Single URI, single HTTP method (POST). (e.g., SOAP/RPC)
Level 1: Resources - Distinct URIs for distinct resources. (/api/users, /api/orders)
Level 2: HTTP Verbs - Correct use of GET, POST, PUT, DELETE, PATCH. Correct status codes. (DRF default)
Level 3: Hypermedia Controls (HATEOAS) - API responses include links guiding the client on what to do next.
```

## 2. Idempotency

**Idempotent**: Making multiple identical requests has the same effect as making a single request.

- `GET`, `PUT`, `DELETE`, `HEAD`, `OPTIONS` are strictly idempotent.
- `POST`, `PATCH` (mostly) are NOT idempotent.

If a network timeout occurs during a `POST /payments/`, retrying might charge the user twice.
**Fix**: Use Idempotency Keys (e.g., `Idempotency-Key` header) mapped to a cache or DB to prevent duplicate processing.

## 3. Standardized Error Payloads (RFC 7807)

DRF's default errors are dicts of field names and arrays of strings. For production, unify errors using RFC 7807 (Problem Details for HTTP APIs).

```python
# Custom Exception Handler
from rest_framework.views import exception_handler
from rest_framework.response import Response

def rfc7807_exception_handler(exc, context):
    response = exception_handler(exc, context)
    
    if response is not None:
        custom_data = {
            "type": "https://api.example.com/errors/validation-error",
            "title": "Your request parameters didn't validate.",
            "status": response.status_code,
            "detail": "See 'invalid_params' for more info.",
            "invalid_params": response.data
        }
        response.data = custom_data
        response['Content-Type'] = 'application/problem+json'
        
    return response
```

## 4. The HATEOAS Reality Check

While Level 3 (HATEOAS) is the "purest" REST, modern SPA (React/Vue/Angular) clients rarely use it because API routes and capabilities are often hardcoded in the frontend logic.
In DRF, `HyperlinkedModelSerializer` provides HATEOAS links, but it increases serialization time. Use it only if you have a genuine dynamic client architecture; otherwise, `ModelSerializer` with ID references is the industry standard.

## 5. Nesting vs Flat Resources

### 🔴 Anti-pattern: Deep Nesting
`/api/users/1/orders/5/items/12/reviews/`
Hard to route, hard to cache, hard to query.

### 🟢 Best Practice: Flat Resources
`/api/reviews/?item=12`
Easier to paginate, filter, and reuse endpoints. Max depth should usually be 1 level (`/api/users/1/orders/`).

## 6. Production Checklist
- [ ] Custom exception handler enforces consistent error schema (like RFC 7807).
- [ ] Idempotency keys are required for financially sensitive `POST` endpoints.
- [ ] Endpoint structures are flat, avoiding deeply nested hierarchies.
- [ ] Appropriate HTTP status codes are used (201 Created, 204 No Content, 401 Unauthorized, 403 Forbidden, 404 Not Found).
