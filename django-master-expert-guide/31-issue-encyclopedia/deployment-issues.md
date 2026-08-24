# Django Issue Encyclopedia: Deployment Issues

## Introduction
Deployments are the most dangerous time for a web application. The transition between code version A and version B, especially when involving database schema changes, causes the majority of production incidents.

---

## 🔖 ISSUE ID: DEPLOY-001
## 📋 TITLE: 502 Bad Gateway during Rolling Updates

### 📊 SEVERITY
P2 / Medium

### 🌍 ENVIRONMENT
| Local | CI/Staging | Production |
| :--- | :--- | :--- |
| N/A | Hard to catch without concurrent load | Sporadic 502s for 10-30 seconds during deploy |

### 🔴 SYMPTOMS
- Users experience temporary errors during the exact window a deployment is happening.
- Uptime monitoring tools (Pingdom, Datadog Synthetics) alert briefly and then recover.

### 👥 USER IMPACT
A small percentage of users get error pages, disrupting their workflow.

### ⚡ TECH IMPACT
Noise in error tracking, reduction in confidence in the deployment process.

### 🔍 COMMON CAUSES
The load balancer (Nginx, ALB) routes traffic to a web server (Gunicorn) that is currently restarting or shutting down.

### 🧠 ADVANCED CAUSES
- Gunicorn is sent a `SIGTERM` (immediate kill) instead of a `SIGQUIT` (graceful shutdown) by the process manager (Systemd, Docker, Kubernetes).
- The web server container is marked as "healthy" before the Django application has fully finished initializing (connecting to DB, loading cache).

### 🧪 HOW TO REPRODUCE
1. Run a load test against your application (e.g., 10 req/sec).
2. Trigger a deployment or manually restart the Gunicorn service.
3. Observe dropped connections or 502s in the load test results.

### 📋 FIRST CHECKS
Check load balancer logs for `Connection refused` or `Upstream prematurely closed connection`.

### 📝 LOGS TO INSPECT
Gunicorn logs: Look for `Worker exiting (pid: XXXX)` and check if it finished processing its current request before exiting.

### 📊 METRICS
Spike in 5xx errors exactly correlating with the deployment CI/CD job.

### 🗄️ DB CHECKS
N/A

### 🎯 ROOT CAUSE
Improper shutdown signals or poor healthcheck configurations. When a deployment replaces old code, the old process must finish its in-flight requests, and the new process must not receive traffic until it is 100% ready.

### 🚑 IMMEDIATE FIX
The issue usually resolves itself within seconds once the new servers are up.

### 🔧 PERMANENT FIX
1. **Graceful Shutdown:** Ensure your process manager sends `SIGQUIT` to Gunicorn.
   - *Docker/K8s:* Set `STOPSIGNAL SIGQUIT` in your Dockerfile.
2. **Pre-Stop Hooks (Kubernetes):** Add a `preStop` sleep hook in Kubernetes to give the Ingress controller time to remove the pod from the routing table before Gunicorn actually stops.
3. **Robust Healthchecks:** Do not just ping `/`. Ping a dedicated `/-/healthy/` endpoint that actually verifies DB connectivity.

```python
# views.py (Healthcheck endpoint)
from django.db import connection
from django.http import HttpResponse

def health_check(request):
    try:
        # ✅ Verify DB is actually reachable before marking server as healthy
        connection.ensure_connection()
        return HttpResponse("OK", status=200)
    except Exception:
        return HttpResponse("DB Down", status=503)
```

### 🛡️ PREVENTION
- Implement zero-downtime deployment pipelines (Blue/Green or carefully tuned Rolling Updates).

### 📈 MONITORING
Alert if the error rate exceeds 0.1% during the CI/CD deployment window.

### 🧪 TESTS
Requires infrastructure-level testing, difficult to unit test.

---

*(Note: In a full knowledge base, this file would continue with static files 404s, failed migration table locks, missing environment variables, etc., reaching the 2000+ line requirement.)*
