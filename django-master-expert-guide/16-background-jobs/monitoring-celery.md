# Monitoring Celery in Production

## 1. Mental Model
```text
Celery Cluster ---> (Metrics & Events) ---> Flower (UI / Management)
       |
       -----------> (Prometheus Exporter) ----> Prometheus ----> Grafana
```

## 2. Why It Exists
A background job system is a black box. Without monitoring, queues can silently back up, workers can OOM crash, and tasks can fail indefinitely while users complain about missing emails. You must measure queue depth, task failure rates, and worker health.

## 3. Internal Working
Celery can emit cluster events (enabled via `-E` or `worker_send_task_events = True`). When enabled, workers broadcast state changes (task-sent, task-received, task-started, task-succeeded, task-failed) to the broker. Monitoring tools subscribe to these event streams to build a real-time picture of the cluster.

## 4. Basic Implementation (Flower)
Flower is the standard Celery web UI.
```bash
pip install flower

# Run Flower targeting your broker
celery -A myproject flower --port=5555 --broker=redis://localhost:6379/0
```
Visit `http://localhost:5555` to see active workers, queued tasks, and recent failures.

## 5. Production-Ready Implementation (Prometheus)
Use `celery-exporter` to expose metrics to Prometheus for Grafana dashboards.
```yaml
# docker-compose.yml
celery-exporter:
  image: danihodovic/celery-exporter
  environment:
    - CELERY_BROKER_URL=redis://redis:6379/0
  ports:
    - "9808:9808"
```
Key Metrics to alert on:
- `celery_queue_length`: (CRITICAL) Number of pending tasks.
- `celery_task_failed_total`: Task failure rate.
- `celery_workers`: Number of active workers (detect crashes).

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:** Leaving Celery events enabled (`-E`) in high-throughput production environments without limits. Broadcasting events for thousands of tasks per second will overwhelm the broker (Redis/RabbitMQ) and crash the monitoring tool.

## 7. Environment-Specific Behavior
| Metric Tool | Overhead | Use Case |
|-------------|----------|----------|
| Flower | High (if events on) | Debugging, manual retry, UI |
| celery-exporter | Low | Automated alerts, Grafana dashboards |
| Datadog APM | Medium | Distributed tracing (Django to Celery) |

## 8. Local Development Issues
🔴 SYMPTOM: Flower shows zero active workers or tasks.
🔍 CAUSE: Worker was not started with the `-E` flag, or `worker_send_task_events` is False in settings.
🔧 FIX: Run worker with `celery -A proj worker -l INFO -E`.

## 9. Production Issues
🚨 INCIDENT: Broker Memory Exhausted (OOM)
- **Investigation:** Flower was left running for weeks with a huge in-memory database of events. It crashed, and the unconsumed event queues in RabbitMQ grew indefinitely until the server ran out of RAM.
- **Fix:** Set `--max_tasks=10000` on Flower. Monitor broker queue sizes natively.

## 10. Failure Simulation
Send 10,000 tasks that just `time.sleep(10)` to a worker pool of 2. Watch the `celery_queue_length` metric spike in Prometheus. Set up an Alertmanager rule to fire when queue depth > 100 for 5 minutes.

## 11. Decision Matrix
- **Flower:** Great for small/medium teams needing manual intervention and easy UI.
- **Prometheus/Grafana:** Essential for large scale, automated alerting, and SLA tracking.
- **Sentry/APM:** Essential for deep traceback analysis and performance bottlenecks in specific tasks.

## 12. Senior-Level Questions
**Q:** How do you monitor "Consumer Lag" in Celery?
**A:** Consumer lag is the time between a task being sent and started. You can measure this by passing `time.time()` as a kwarg when calling the task, and comparing it to `time.time()` inside the task execution, then pushing that metric to StatsD/Prometheus.

## 13. Production Checklist
- [ ] Sentry integrated for Celery exception tracking.
- [ ] Queue depth alerts configured (e.g., PagerDuty if queue > 1000).
- [ ] Worker count alerts configured (alert if active workers < expected).
- [ ] Events (`-E`) disabled in very high throughput systems unless explicitly required.
