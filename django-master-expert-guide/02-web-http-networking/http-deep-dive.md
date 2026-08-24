# HTTP Deep Dive for Django Engineers

## 1. Mental Model: The HTTP Protocol and Django

```text
+----------------+                       +-------------------+
|     Client     |     HTTP Request      |  Django Server    |
|  (Browser/App) | --------------------> | (WSGI/ASGI + App) |
|                |   GET /api/users/     |                   |
|                |   Host: api.com       | 1. WSGI Handler   |
|                |   Authorization: ...  | 2. Middleware     |
|                |                       | 3. URL Router     |
|                | <-------------------- | 4. View           |
|                |    HTTP Response      |                   |
|                |   200 OK              |                   |
|                |   Content-Type: json  |                   |
|                |   {"users": [...]}    |                   |
+----------------+                       +-------------------+
```

HTTP is the foundational language of the web. Django’s core responsibility is parsing an incoming raw HTTP string into a Python `HttpRequest` object, routing it, processing it, and returning an `HttpResponse` object, which is then serialized back into a raw HTTP string by the application server (Gunicorn/Uvicorn).

## 2. Why It Exists

HTTP provides a stateless, text-based (in 1.1) or binary (in 2/3) protocol for resource exchange. Django abstracts away the raw socket parsing, handling byte streams, chunked encoding, and header case-insensitivity, allowing you to focus on business logic. 

**Alternatives:** WebSockets (for stateful bidirectional streaming), gRPC (for strict contract binary internal communication). HTTP remains dominant due to universal client support, caching infrastructure (CDNs), and REST semantics.

## 3. Internal Working: Request Flow

When an HTTP request hits Django [DJANGO 6.1+]:

1. **WSGI/ASGI Server**: Receives TCP packet, parses HTTP bytes.
2. **`django.core.handlers.wsgi.WSGIHandler`**: Constructs `HttpRequest`.
   - Reads `environ` dict.
   - Populates `request.META` (headers mapping).
   - Defers `request.body` reading (lazy evaluation) to avoid memory spikes.
3. **Middleware Chain**: Processes request (e.g., `AuthenticationMiddleware` reads `Cookie` header).
4. **View**: Accesses `request.method`, `request.GET`, returns `HttpResponse`.
5. **Middleware Chain**: Processes response (e.g., `CommonMiddleware` adds `Content-Length`).
6. **WSGI/ASGI Server**: Serializes `HttpResponse` into HTTP bytes.

## 4. HTTP Versions and Django Implications

| Protocol | Transport | Multiplexing | Django Implication |
| :--- | :--- | :--- | :--- |
| **HTTP/1.1** | TCP | No (Head-of-line blocking) | Needs multiple concurrent workers (Gunicorn threads/processes). |
| **HTTP/2** | TCP | Yes (Streams) | Terminated at Nginx/ALB. Django app still receives HTTP/1.1 via reverse proxy. Enables efficient parallel static file loading without domain sharding. |
| **HTTP/3** | UDP (QUIC) | Yes (No TCP HoL blocking) | Terminated at Cloudflare/ALB. Excellent for mobile clients with spotty networks. Transparent to Django. |

## 5. Basic Implementation vs Production

### Basic View (Not Production Ready)
```python
from django.http import HttpResponse, HttpRequest

def basic_view(request: HttpRequest) -> HttpResponse:
    # Ignores methods, no error handling, blocks thread if doing IO
    return HttpResponse("Hello World", content_type="text/plain")
```

### Production-Ready View
```python
from django.http import JsonResponse, HttpRequest, HttpResponseNotAllowed
from django.views.decorators.http import require_http_methods
import logging

logger = logging.getLogger(__name__)

@require_http_methods(["GET"])  # Enforces HTTP verb semantics
def prod_view(request: HttpRequest) -> JsonResponse:
    # 1. Access Request Headers safely
    client_id = request.headers.get('X-Client-ID')
    
    # 2. Content Negotiation (Manual or via DRF)
    accepts = request.headers.get('Accept', '')
    if 'application/json' not in accepts and '*/*' not in accepts:
        return JsonResponse({"error": "Not Acceptable"}, status=406)

    try:
        # Business logic here
        data = {"message": "Success", "client": client_id}
        
        # 3. Construct Response with Cache Control & ETag
        response = JsonResponse(data, status=200)
        response['Cache-Control'] = 'public, max-age=300'
        # Vary on headers that change the response
        response['Vary'] = 'Accept, X-Client-ID'
        return response
    except Exception as e:
        logger.exception("Unexpected error in prod_view")
        return JsonResponse({"error": "Internal Server Error"}, status=500)
```

## 6. HTTP Methods (Idempotency and Safety)

- **GET**: Safe, Idempotent. Used for retrieval. (Never mutate state in a GET request).
- **POST**: Unsafe, Non-idempotent. Used for creation or complex processing.
- **PUT**: Unsafe, Idempotent. Replaces a resource completely.
- **PATCH**: Unsafe, Non-idempotent (usually). Partial update.
- **DELETE**: Unsafe, Idempotent. Removes a resource.
- **HEAD**: Safe, Idempotent. Like GET but returns headers only (Django handles this automatically if you support GET).
- **OPTIONS**: Safe, Idempotent. Returns allowed methods and CORS info.

## 7. Status Codes Deep Dive

- **2xx (Success)**: `200 OK`, `201 Created` (after POST), `204 No Content` (after DELETE).
- **3xx (Redirection)**: 
  - `301 Moved Permanently`: Cached heavily by browsers. Use with caution.
  - `302 Found`: Temporary. 
  - `304 Not Modified`: Used with ETag/Last-Modified for caching.
- **4xx (Client Error)**:
  - `400 Bad Request`: Validation failure.
  - `401 Unauthorized`: Missing/invalid authentication.
  - `403 Forbidden`: Authenticated, but lacks permissions (or CSRF failure).
  - `404 Not Found`: Django's `Http404`.
  - `405 Method Not Allowed`: Handled by `@require_http_methods`.
  - `429 Too Many Requests`: Rate limiting (DRF `Throttling`).
- **5xx (Server Error)**:
  - `500 Internal Server Error`: Unhandled exception.
  - `502 Bad Gateway`: Nginx couldn't talk to Gunicorn.
  - `504 Gateway Timeout`: Gunicorn worker took too long and Nginx aborted.

## 8. Headers That Matter

Django parses HTTP headers and places them in `request.headers` (a case-insensitive mapping available since Django 2.2). Before that, they were in `request.META` as `HTTP_HEADER_NAME`.

- **Content-Type**: What the client sent (e.g., `application/json`).
- **Accept**: What the client wants (Content Negotiation).
- **Authorization**: `Bearer <token>`.
- **X-Forwarded-For**: Client IP chain when behind proxies. Django uses this to resolve real IPs (requires `SECURE_PROXY_SSL_HEADER` config).
- **X-Request-ID**: Used for distributed tracing.

## 9. HTTP Caching in Django

Caching saves database hits and CPU.

```python
from django.views.decorators.cache import cache_control
from django.views.decorators.http import condition

def my_etag(request, *args, **kwargs):
    return "W/\"my-unique-hash\""

@condition(etag_func=my_etag)
@cache_control(max_age=3600, public=True)
def cached_view(request):
    # If client sends If-None-Match: W/"my-unique-hash", 
    # Django intercepts and returns 304 Not Modified without running view logic.
    return HttpResponse("Heavy processing result")
```

## 10. Streaming and Large Files

Standard `HttpResponse` loads the entire body into memory. For large files or slow generation, use `StreamingHttpResponse`.

```python
from django.http import StreamingHttpResponse
import time

def stream_generator():
    for i in range(10):
        yield f"Chunk {i}\n".encode('utf-8')
        time.sleep(1)

def streaming_view(request):
    # Uses Transfer-Encoding: chunked
    return StreamingHttpResponse(stream_generator(), content_type="text/plain")
```
*Note:* Gunicorn must use async workers (like `gevent` or `uvicorn`) for streaming, otherwise sync workers will be blocked for the duration of the stream.

## 11. Anti-Patterns

### 💣 The Ticking Time Bomb: Reading entire large body in memory
```python
# Bad
data = request.body  # Crash if body is 5GB!
```
**Fix:** Nginx should enforce `client_max_body_size`, and Django should stream uploads (`DATA_UPLOAD_MAX_MEMORY_SIZE`).

## 12. Environment-Specific Behavior

| Environment | HTTP Behavior | Notes |
| :--- | :--- | :--- |
| **Local (runserver)** | HTTP/1.1 | Single-threaded by default, bad at concurrent streaming. |
| **Docker (Gunicorn Sync)** | HTTP/1.1 | 1 request per worker. Slow HTTP clients tie up workers (Slowloris attack). |
| **Prod (Nginx + Gunicorn)** | Nginx terminates HTTP/2, talks HTTP/1.0 to Gunicorn | Nginx buffers slow requests, protecting Gunicorn. |

## 13. Production Issues

### 🔴 INCIDENT: 504 Gateway Timeout on File Uploads
**Severity**: High
**Investigation**: Clients report timeouts uploading 10MB images. Nginx logs show 504. Gunicorn logs show worker timeout.
**Root Cause**: Gunicorn worker timeout was 30s. Client upload speed was 100kbps, taking 100s. Gunicorn sync worker blocked.
**Fix**: 
1. Use Nginx proxy buffering (Nginx buffers the file to disk before sending to Gunicorn).
2. Switch to an object storage direct upload (Presigned S3 URLs) to bypass Django for large blobs completely.

### 🔴 SYMPTOM: Request IP is always 127.0.0.1
**Cause**: The application is behind a Load Balancer / Nginx, and Django doesn't know it.
**Reproduce**: Log `request.META['REMOTE_ADDR']`.
**Debug/Fix**: 
Enable proxy headers in Nginx: `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`
In Django `settings.py`:
```python
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
```
(And use a middleware like `django-ipware` for safe extraction to prevent IP spoofing).

## 14. Checklist for Production
- [ ] Enforce `ALLOWED_HOSTS`.
- [ ] Implement rate limiting (429 responses).
- [ ] Configure `DATA_UPLOAD_MAX_MEMORY_SIZE` (default 2.5MB).
- [ ] Set `SECURE_PROXY_SSL_HEADER` if behind a proxy.
- [ ] Use `X-Request-ID` tracing middleware for correlation in logs.
