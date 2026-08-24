# Debugging Production Systems

## 1. Mental Model
Debugging in production requires zero-downtime introspection. You cannot halt execution with a breakpoint; you must rely on telemetry, profiling, and safe read-only queries.

## 2. Distributed Tracing & Log Correlation
Inject a `Trace-Id` header at the edge (Nginx) and propagate it through Django via middleware.

```python
# middleware.py
import uuid
import threading

request_local = threading.local()

class TraceIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        trace_id = request.headers.get('X-Trace-Id', str(uuid.uuid4()))
        request_local.trace_id = trace_id
        response = self.get_response(request)
        response['X-Trace-Id'] = trace_id
        return response
```

## 3. Live Profiling with `py-spy`
`py-spy` allows you to profile a running Python process without restarting or modifying code.

```bash
# Find the gunicorn worker PID
ps aux | grep gunicorn
# Generate a flamegraph
sudo py-spy record -o profile.svg --pid 12345
```

## 4. Production Issues
🔴 **INCIDENT: CPU Spikes to 100%**
- **Severity:** High
- **Investigation:** Used `py-spy top --pid 12345` and found the process stuck in a regex match.
- **Root Cause:** Catastrophic backtracking in a URL router regex.
- **Fix:** Rewrote regex to be non-backtracking and deployed hotfix.

## 5. Anti-Patterns
🔴 **TICKING TIME BOMB: Using `pdb` in Production**
Never leave a `breakpoint()` in production code. It will halt the Gunicorn worker, causing request queuing and eventually a 502 Bad Gateway.

