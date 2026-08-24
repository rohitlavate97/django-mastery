# Circuit Breaker Pattern in Django

## 1. Mental Model
```text
[Django View] -> [Circuit Breaker] -> [External Service]
                        |
                 +------+------+
                 |             |
              (CLOSED)      (OPEN) --(Fast Fail)--> [Fallback Response]
                 |             |
           (Traffic OK)  (Errors > Threshold)
                 |             |
                 +----(HALF-OPEN)----+
                      (Testing)
```
A Circuit Breaker is an automated switch that stops traffic to a failing service. It prevents your system from repeatedly calling a service that is known to be down, saving resources and allowing the external service time to recover.

## 2. Why It Exists
In microservice architectures, cascading failures are deadly. If Service A depends on Service B, and Service B slows down, Service A will exhaust its worker threads waiting for B. A circuit breaker "trips" after successive failures, instantly failing future requests (Open state) without blocking.

## 3. Internal Working
The breaker tracks failure rates over a rolling window.
- **Closed**: Normal operation. Requests pass through.
- **Open**: Threshold breached. Requests fail immediately (e.g., throwing a `CircuitBreakerError`).
- **Half-Open**: After a timeout, allows a limited number of requests through to test if the service has recovered. If successful, resets to Closed. If failed, returns to Open.

## 4. Basic Implementation
```python
# 🔴 ANTI-PATTERN: Manual error counting
failures = 0

def call_service():
    global failures
    if failures > 5:
        raise Exception("Service down")
    
    try:
        response = requests.get("http://api.example.com")
        failures = 0
        return response
    except Exception:
        failures += 1
        raise
```
*Why it's bad:* Not thread-safe, state lost on worker restart, no half-open testing, no time window.

## 5. Production-Ready Implementation
Using the `pybreaker` library backed by Redis for distributed state across all Django workers.

```python
# ✅ PRODUCTION-READY
import pybreaker
import redis
import httpx
from django.conf import settings
from django.http import JsonResponse

# Use Redis so the breaker state is shared across all Gunicorn/uWSGI workers
redis_conn = redis.StrictRedis.from_url(settings.REDIS_URL)

# Configure breaker: Trip after 5 failures, wait 60s before half-open
payment_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    state_storage=pybreaker.CircuitRedisStorage(pybreaker.STATE_CLOSED, redis_conn, namespace='payment_cb')
)

@payment_breaker
def execute_payment(amount, token):
    """
    Calls the external payment gateway.
    """
    response = httpx.post("https://api.gateway.com/charge", json={"amount": amount, "token": token}, timeout=5.0)
    response.raise_for_status()
    return response.json()

def checkout_view(request):
    try:
        result = execute_payment(100, "tok_123")
        return JsonResponse({"status": "success", "data": result})
    except pybreaker.CircuitBreakerError:
        # The breaker is OPEN. Fast failure.
        return JsonResponse({"status": "error", "message": "Payment system temporarily unavailable. Try again later."}, status=503)
    except httpx.HTTPError:
        # The request actually failed (but hasn't tripped the breaker yet)
        return JsonResponse({"status": "error", "message": "Payment failed."}, status=502)
```

## 6. Anti-Patterns
🔴 **In-Memory State:** Using memory storage (the default in most libraries) means each Gunicorn worker has its own circuit breaker. If you have 10 workers and a threshold of 5, you might need 50 failures before all workers trip!
🔴 **Tripping on Client Errors:** Configuring the breaker to trip on 400 Bad Request. Breakers should only trip on infrastructure failures (Timeouts, 502, 503, 504), not business logic errors.

## 7. Environment-Specific Behavior
| Environment | Behavior | Consideration |
|-------------|----------|---------------|
| Local | Often uses memory storage | Can use Redis if running via docker-compose |
| Staging | Identical to Prod | Perfect for chaos testing the breaker |
| Production | Redis-backed | Requires monitoring metrics on breaker state changes |

## 8. Local Development Issues
🔴 **SYMPTOM:** Breaker resets randomly or doesn't trip when expected.
🔍 **CAUSE:** You are using in-memory state and Django's auto-reloader restarted the worker, wiping the state.
🔧 **FIX:** Use a Redis-backed storage for the circuit breaker even locally.

## 9. Production Issues
🔴 **INCIDENT:** API completely stopped processing payments even though the gateway recovered.
* **Severity:** High
* **Investigation:** The external gateway was down for 10 minutes. The breaker tripped. When the gateway came back, the breaker remained Open permanently.
* **Root Cause:** A bug in the half-open transition logic when using an outdated Redis library version.
* **Fix:** Upgraded `pybreaker` and added explicit Datadog alerts triggering when the breaker remains Open for > 5 minutes.

## 10. Failure Simulation
Block traffic to the external service using `iptables` or a proxy tool like Toxiproxy. Send 6 requests. The first 5 should timeout. The 6th should instantly throw a `CircuitBreakerError`.

## 11. Decision Matrix
| Storage Backend | Pros | Cons |
|-----------------|------|------|
| Memory | Zero config, fast | State per-worker, lost on restart |
| Redis | Shared state, persistent | Network hop, requires Redis infra |
| Service Mesh (Envoy/Istio) | No code changes needed | Complex infrastructure |

## 12. Senior-Level Questions
**Q: How do you handle fallback responses when a circuit breaker trips on a non-critical service (e.g., a recommendation engine)?**
A: Instead of returning a 503 error, the view should catch the `CircuitBreakerError` and gracefully degrade. For a recommendation engine, you can return a statically cached list of popular items, or simply an empty list, allowing the main page to load successfully even if the personalization feature is dead.

## 13. Production Checklist
- [ ] Redis (or shared storage) used for breaker state.
- [ ] Breaker configured to ignore 4xx client errors.
- [ ] Fallback responses implemented where applicable.
- [ ] Metrics/logging emitted on state transitions (Closed -> Open).
