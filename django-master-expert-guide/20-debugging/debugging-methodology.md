# 12-Step Systematic Debugging Framework

## 1. Mental Model
Debugging in Django requires understanding the full lifecycle of a request from the reverse proxy (Nginx) through the WSGI/ASGI server (Gunicorn/Uvicorn), into Django's middleware stack, URL routing, view processing, ORM interactions, and response generation.

```text
[Client] -> [Load Balancer] -> [Nginx] -> [Gunicorn] -> [Django Middleware] -> [Django View] -> [Django ORM] -> [PostgreSQL]
```

## 2. Why It Exists
Complex systems fail in complex ways. Relying on "guess and check" leads to wasted hours and worse, creating new bugs. The 12-Step Framework provides a deterministic approach to root cause analysis.

## 3. The 12-Step Framework
1. **Acknowledge and Secure:** Stop the bleeding. If production is down, revert the last deploy or scale up resources before debugging.
2. **Reproduce the Issue:** Find the exact sequence of events that triggers the failure reliably.
3. **Isolate the Scope:** Is it frontend, network, infrastructure, database, or application code?
4. **Gather Telemetry:** Pull logs, traces, and metrics.
5. **Formulate Hypotheses:** List 3 possible causes.
6. **5-Whys Root Cause Analysis:** Drill down to the fundamental issue.
7. **Test Hypotheses:** Use safe testing environments.
8. **Fix the Root Cause:** Apply the minimal required patch.
9. **Verify the Fix:** Ensure the issue is resolved without regressions.
10. **Deploy:** Roll out the fix safely.
11. **Monitor:** Watch telemetry for anomalies.
12. **Preventive Measures:** Write tests, add constraints, update runbooks.

## 4. 5-Whys Root Cause Analysis Example
- **Why did the API timeout?** The database query took 45 seconds.
- **Why did it take 45 seconds?** It performed a sequential scan on a 50M row table.
- **Why was it a sequential scan?** There was no index on the filtered column.
- **Why was there no index?** The migration adding the index failed silently due to a lock timeout.
- **Why did it fail silently?** Our deployment pipeline ignores migration exit codes.

## 5. Local vs Production Debugging
| Environment | Tools | Safe Actions |
|-------------|-------|--------------|
| Local | `pdb`, `ipdb`, Django Debug Toolbar | Step-through execution, breaking changes |
| Production | Logs, APM, Sentry, `py-spy` | Read-only DB queries, trace analysis |

## 6. Anti-Patterns
🔴 **TICKING TIME BOMB: Blindly Restarting Services**
Restarting a service clears the memory state and hides the symptom without fixing the cause. It guarantees the issue will return.

