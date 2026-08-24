# Python Memory Model for Django Engineers

## 1. Mental Model
```text
+-------------------------------------------------------+
|   Python Object (e.g. Django Model Instance)          |
|   - Type Pointer (e.g. User)                          |
|   - Reference Count (gc)                              |
|   - Value / __dict__                                  |
+-------------------------------------------------------+
```
Memory in Python is managed primarily by **Reference Counting**. When an object's reference count drops to 0, it is immediately deallocated. A secondary **Garbage Collector** cleans up reference cycles.

## 2. Object Lifecycle in a Django Request
1. Request arrives. Django creates `HttpRequest` object (ref count = 1).
2. URL resolution passes `request` to the view (ref count = 2).
3. View queries DB: `User.objects.all()`. Django fetches rows, creates `User` instances.
4. Response is generated and returned.
5. `request`, `User` instances, and response objects lose references. Ref counts hit 0. Memory freed.

## 3. Common Memory Leaks in Django

### Anti-Pattern 1: QuerySet Caching
Django QuerySets cache their results after evaluation.
```python
# 🔴 TICKING TIME BOMB: Loads all millions of users into memory.
def export_all_users():
    users = User.objects.all()
    for user in users:  # Evaluates and caches all rows in memory
        write_to_csv(user)

# ✅ PRODUCTION FIX: Use iterator() to prevent caching.
def export_all_users():
    users = User.objects.all().iterator(chunk_size=2000)
    for user in users:  # Memory stays flat!
        write_to_csv(user)
```

### Anti-Pattern 2: Signal Handlers without Weak References
Django signals use `weakref` to connect receivers by default, preventing leaks. But if you connect a bound method (a method of an instance) without `weak=False`, it gets garbage collected unexpectedly. Conversely, keeping strong references to objects in module-level lists causes permanent memory leaks.

## 4. Memory Profiling Tools
- **tracemalloc**: Standard library tool to trace memory blocks.
- **objgraph**: Visualizes reference cycles.
- **memory_profiler**: Line-by-line memory usage.

### Debugging a Leak (Local/Staging)
🔴 **SYMPTOM**: Gunicorn worker memory keeps growing until OOM (Out Of Memory) kill.
🔍 **CAUSE**: `DEBUG = True` in production. Django's `django.db.backends` stores ALL SQL queries in memory when DEBUG=True.
🔧 **FIX**: NEVER run `DEBUG = True` in production.

## 5. Why Django Processes Grow (Memory Fragmentation)
Even with perfect code, a Python process might grow in memory (Resident Set Size - RSS) because:
1. Python allocators (pymalloc) request memory from OS in arenas.
2. Freeing small objects doesn't return arenas to OS immediately (fragmentation).
3. Max memory watermark remains high.

**✅ Production Workaround**: Use `max_requests` in Gunicorn.
```ini
# gunicorn.conf.py
max_requests = 1000
max_requests_jitter = 50 # Prevents all workers from restarting at once
```
This intentionally kills and respawns workers periodically, providing a clean memory slate.

## 6. RSS vs VSZ vs PSS
- **VSZ (Virtual Memory)**: Total memory requested by process. Mostly irrelevant.
- **RSS (Resident Set Size)**: Physical RAM currently used. The most important metric.
- **PSS (Proportional Set Size)**: RSS adjusted for shared pages (important in pre-forking Gunicorn).

## 7. Production Checklist
- [ ] `DEBUG = False` is enforced in staging and production.
- [ ] Large batch jobs use `.iterator(chunk_size=...)`.
- [ ] Gunicorn uses `max_requests` to mitigate fragmentation.
- [ ] `update()` and `delete()` bulk operations are used instead of iterating and saving instances.
