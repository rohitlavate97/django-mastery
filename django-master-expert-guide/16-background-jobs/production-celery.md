# Production Celery: Concurrency & Stability

## 1. Mental Model
```text
Worker Node (e.g., 8 CPU Cores)
 ├── Prefork (Default): 8 isolated Python processes. Best for CPU-bound (math, image processing).
 ├── Gevent: 1 process, 1000s of green threads. Best for I/O-bound (network, APIs).
 └── Threads: 1 process, OS threads. Good for mixed I/O where gevent fails.
```

## 2. Why It Exists
Different tasks have vastly different resource requirements. Compressing a video blocks the CPU. Waiting for a slow third-party API uses 0% CPU but blocks the thread. Choosing the wrong concurrency model wastes money or destroys performance.

## 3. Internal Working
- **Prefork (`-P prefork`)**: Celery spawns `n` child processes using `multiprocessing`. Bypasses the GIL. Memory heavy.
- **Gevent (`-P gevent`)**: Uses monkey-patching to make synchronous Python I/O non-blocking. Single process, highly memory efficient.
- **Threads (`-P threads`)**: Uses Python's `concurrent.futures`. Subject to GIL, but safer than gevent for complex C-extensions.

## 4. Basic Implementation (CLI)
```bash
# CPU Bound Worker
celery -A myproject worker -Q math_queue -P prefork -c 4

# I/O Bound Worker
celery -A myproject worker -Q api_queue -P gevent -c 500
```

## 5. Production-Ready Implementation (Configuration)
Combat Python memory leaks and ensure graceful shutdown.
```python
# settings.py
# Restart worker process after 1000 tasks to prevent memory leaks
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# OR restart if a process consumes more than 250MB RAM
CELERY_WORKER_MAX_MEMORY_PER_CHILD = 250000 

# Prefetch only 1 task at a time for long-running tasks to prevent starvation
CELERY_WORKER_PREFETCH_MULTIPLIER = 1 

# Allow tasks 5 minutes to finish during worker shutdown
CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS = True
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:** Using `-P gevent` with libraries that use C-extensions heavily (like `psycopg2-binary` without proper setup, or `numpy`). Gevent cannot monkey-patch C-level blocking operations, which will freeze the entire gevent worker.

## 7. Environment-Specific Behavior
| Model | Memory per Concurrency Unit | GIL Affected | Best Use Case |
|-------|-----------------------------|--------------|---------------|
| Prefork | ~50MB - 200MB+ | No | Machine Learning, Image processing |
| Gevent | ~50KB | Yes | Scraping, 1000s of API calls |
| Threads | ~1MB - 5MB | Yes | Database heavy sync tasks |

## 8. Local Development Issues
🔴 SYMPTOM: Gevent worker crashes on startup.
🔍 CAUSE: Gevent monkey-patching must happen extremely early, often before other modules are imported.
🔧 FIX: Ensure gevent is installed, and rely on Celery's CLI to handle the patching natively via `-P gevent`.

## 9. Production Issues
🚨 INCIDENT: Worker Stuck, Refusing to Die
- **Investigation:** A deployment triggered a worker restart (SIGTERM). The worker waited for active tasks to finish. One task was stuck on a `requests.get()` without a timeout. The worker hung indefinitely, blocking deployment.
- **Fix:** ALWAYS enforce timeouts. Set `CELERY_TASK_TIME_LIMIT` and `CELERY_TASK_SOFT_TIME_LIMIT`.

## 10. Failure Simulation
Create a task with `time.sleep(600)`. Send a SIGTERM to the worker (`kill -15 <pid>`). Watch the logs: "Warm shutdown... waiting for tasks to complete". Send a SIGKILL (`kill -9 <pid>`) and see the task get lost (if `acks_late=False`).

## 11. Decision Matrix
- Separate Queues! Route CPU tasks to a `prefork` pool, and API tasks to a `gevent` pool. Never mix them.
```python
CELERY_TASK_ROUTES = {
    'tasks.process_image': {'queue': 'cpu_heavy'},
    'tasks.fetch_urls': {'queue': 'io_heavy'},
}
```

## 12. Senior-Level Questions
**Q:** What is the `prefetch_multiplier` and why is it dangerous?
**A:** It controls how many tasks a worker grabs from the broker at once. If `prefetch=4`, a worker grabs 4 tasks. If task 1 takes 10 hours, tasks 2, 3, and 4 sit waiting in that worker's memory, even if other workers are completely idle! Set it to `1` for long tasks.

## 13. Production Checklist
- [ ] Dedicated queues and concurrency models for I/O vs CPU tasks.
- [ ] `max_tasks_per_child` set to prevent memory leaks.
- [ ] Soft and hard time limits set globally.
- [ ] Always enforce network timeouts (e.g., `requests.get(..., timeout=5)`).
