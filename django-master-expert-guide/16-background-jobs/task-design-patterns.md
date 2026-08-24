# Celery Task Design Patterns

## 1. Mental Model
```text
Task Patterns
├── Simple Tasks (async fire-and-forget)
├── Chains (Sequential A -> B -> C)
├── Groups (Parallel A, B, C)
└── Chords (Parallel A, B, C -> Then D)
```

## 2. Why It Exists
Complex asynchronous workflows cannot be modeled as simple fire-and-forget tasks. You need ways to chain tasks, run them in parallel, and aggregate results without blocking workers.

## 3. Internal Working
Celery implements these patterns using Canvas Primitives. Signatures (`s()` or `si()`) encapsulate the arguments, kwargs, and execution options of a task so it can be passed around and executed later.

## 4. Basic Implementation
```python
from celery import chain, group, chord

# Signature
task_sig = my_task.s(arg1, arg2)

# Chain
chain_res = chain(task1.s(), task2.s(), task3.s())()

# Group
group_res = group(task.s(i) for i in range(10))()
```

## 5. Production-Ready Implementation: Idempotency
```python
import redis
from celery import shared_task

cache = redis.Redis()

@shared_task(bind=True)
def charge_credit_card(self, transaction_id, amount):
    lock_id = f"charge_{transaction_id}"
    
    # Distributed lock to ensure idempotency
    if not cache.set(lock_id, "locked", nx=True, ex=3600):
        return "Already processed"
        
    try:
        # Process charge
        pass
    except Exception as e:
        cache.delete(lock_id) # Release lock on failure
        raise self.retry(exc=e)
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:** Using `s()` instead of `si()` in chains where you don't want the return value of the previous task passed as the first argument to the next task.
```python
# BAD
chain(create_user.s(data), send_email.s(email)) # send_email gets create_user's result!

# GOOD
chain(create_user.s(data), send_email.si(email)) # Immutable signature
```

## 7. Environment-Specific Behavior
| Environment | Redis Result Backend | Memcached |
|-------------|----------------------|-----------|
| Chords | Fully Supported | Supported |
| Groups | Fully Supported | Supported |

## 8. Local Development Issues
🔴 SYMPTOM: Chords hanging forever.
🔍 CAUSE: Result backend not configured or worker missing the `result_backend` setting.
🔧 FIX: Ensure `CELERY_RESULT_BACKEND` is valid.

## 9. Production Issues
🚨 INCIDENT: Redis OOM from Chord Results
- **Investigation:** Celery stores intermediate results for chords in Redis. If the chord is massive, Redis fills up.
- **Fix:** Chunk large datasets. Use `task.chunks()` instead of massive groups.

## 10. Failure Simulation
Simulate a failure in a chain by raising an exception in the second task. Observe that the third task never executes.

## 11. Decision Matrix
- **Chain:** Sequential workflow (Data Prep -> Train -> Evaluate).
- **Group:** Embarrassingly parallel (Scrape 100 URLs).
- **Chord:** Map-Reduce (Scrape 100 URLs -> Aggregate Results).

## 12. Senior-Level Questions
**Q:** How do you handle a chord where some tasks fail?
**A:** Use the `link_error` callback on the chord body, or handle exceptions within the group tasks and return a specific failure dict, allowing the body task to filter them out.

## 13. Production Checklist
- [ ] Signatures used for passing tasks.
- [ ] `si()` used when previous results shouldn't be passed.
- [ ] Idempotency implemented for critical tasks (payments, emails).
- [ ] Result backend configured properly for chords.
