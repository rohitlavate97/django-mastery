# HTTP Client Patterns in Django

## 1. Mental Model
```text
[Django View/Task] --(Request)--> [HTTP Client (httpx/requests)] --(Network)--> [External API]
                                                                        |
[Django View/Task] <--(Response/Error)-- [HTTP Client] <--(Response)----+
```
When Django talks to an external API, it suspends execution and waits. This represents a significant risk. If the external API is slow or unresponsive, your Django application (and its web server workers like Gunicorn/uWSGI) will block, potentially leading to cascading failures.

## 2. Why It Exists
Integrating with external services (payment gateways, CRMs, microservices) is a fundamental requirement. Without robust HTTP client patterns, a single slow external dependency can exhaust your connection pool and take down your entire Django application.

## 3. Internal Working
Django relies on underlying Python HTTP libraries.
- `requests`: Synchronous, widely used, blocking.
- `httpx`: Supports both sync and async, modern API, robust.

When `requests.get()` is called, Python uses `urllib3` which in turn uses socket communication. If no timeout is specified, the socket can block indefinitely.

## 4. Basic Implementation
```python
# 🔴 ANTI-PATTERN: The Ticking Time Bomb
import requests
def fetch_user_data(user_id):
    # No timeout! If the API hangs, this worker hangs forever.
    response = requests.get(f"https://api.example.com/users/{user_id}")
    return response.json()
```

## 5. Production-Ready Implementation
```python
# ✅ PRODUCTION-READY
import httpx
from django.conf import settings
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

# Create a shared client instance for connection pooling
# This should ideally be instantiated at the module level
http_client = httpx.Client(
    timeout=httpx.Timeout(connect=2.0, read=5.0, write=5.0, pool=5.0),
    limits=httpx.Limits(max_keepalive_connections=50, max_connections=100)
)

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException))
)
def fetch_user_data_robust(user_id):
    """
    Fetches user data with explicit timeouts and retries.
    """
    try:
        response = http_client.get(f"https://api.example.com/users/{user_id}")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        # Log the exact status error, don't retry 4xx errors
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"HTTP error {e.response.status_code} for user {user_id}: {e}")
        raise
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:** `requests.get(url)` without `timeout`.
🔴 **Connection Churn:** Creating a new `requests.Session()` or `httpx.Client()` inside a loop or for every single request, defeating connection pooling.

## 7. Environment-Specific Behavior
| Environment | Behavior | Consideration |
|-------------|----------|---------------|
| Local | Fast, mock APIs | Use tools like `responses` or `pytest-httpx`. |
| Docker | Network bridge overhead | DNS resolution issues might surface. |
| CI | Flaky network | Must mock all external HTTP calls. |
| Staging | Slower than prod | Good place to test timeout configurations. |
| Production | Unpredictable | Requires robust timeouts, retries, and circuit breakers. |

## 8. Local Development Issues
🔴 **SYMPTOM:** `httpx.ConnectTimeout` during local dev.
🔍 **CAUSE:** Docker container DNS not resolving the external API, or the API is blocking localhost IPs.
🔧 **FIX:** Verify Docker DNS or use a mock server (e.g., WireMock) locally.

## 9. Production Issues
🔴 **INCIDENT:** Django app became completely unresponsive; Gunicorn workers exhausted.
* **Severity:** High
* **Investigation:** Gunicorn worker logs showed all workers stuck waiting on `requests.post('https://slow-api.com')`.
* **Root Cause:** Missing `timeout` argument in a new third-party integration. The third-party API experienced a 5-minute outage, causing all Django workers to hang.
* **Fix:** Enforce strict timeouts on all HTTP calls and add a linter rule to prevent `requests.*` usage without timeouts.

## 10. Failure Simulation
To intentionally reproduce this failure, run an HTTP server that accepts connections but never sends data (e.g., using `nc -l -p 8080`), and point your Django app to it without a timeout.

## 11. Decision Matrix
| Library | Use Case | Pros | Cons |
|---------|----------|------|------|
| `requests` | Legacy apps, simple scripts | Ubiquitous | Sync only, no strict timeouts by default |
| `httpx` | Modern Django, Async views | Sync/Async, strict defaults | Slightly different API |

## 12. Senior-Level Questions
**Q: How does connection pooling work in `httpx` and how do you ensure Django uses it correctly?**
A: Connection pooling maintains open TCP connections to the target server, reducing the overhead of the TCP handshake and TLS negotiation for subsequent requests. To use it in Django, you must instantiate the `httpx.Client` at the module level (or application level) so it persists across multiple requests processed by the same worker. If you instantiate it inside a view function, the pool is destroyed when the view returns, providing no benefit.

## 13. Production Checklist
- [ ] ALL HTTP calls have explicit `connect` and `read` timeouts.
- [ ] Retries are configured with exponential backoff and jitter.
- [ ] Retries are ONLY applied to idempotent methods (GET, PUT) or specific errors (502, 503, 504), not to non-idempotent POSTs unless safely verifiable.
- [ ] Connection pooling is active (Client instance reused).
- [ ] Sensitive headers (Authorization) are scrubbed from logs.
