# When Async Hurts: The Hidden Costs

## 1. Mental Model
```text
Async Benefits Curve
Performance
   |       /---- (High I/O wait: APIs, WebSockets)
   |      /
   |     /
   |    /   (Simple CRUD) ---> [Sync is often slightly faster!]
   |---/
   |  /
   | /
   |/_______ (CPU Bound tasks) ---> [Async is drastically slower/broken]
   ------------------ Concurrency
```

## 2. Why It Exists
There is a massive hype cycle around "Async Python". Developers often assume `async def` automatically means "faster". In reality, asyncio introduces significant bookkeeping overhead (creating tasks, scheduling callbacks, context switching). If you don't have high I/O latency, this overhead slows you down.

## 3. Internal Working
When Django processes an `async` view that does database operations (without psycopg3 native async), it must:
1. Suspend the event loop task.
2. Package the ORM operation.
3. Submit it to the `sync_to_async` thread pool.
4. Acquire a thread lock.
5. Execute the DB query synchronously.
6. Pass the result back to the event loop.
7. Reschedule the async task.
This crossing of the Sync/Async boundary is extremely expensive compared to just executing the query directly in a WSGI worker.

## 4. Benchmark Reality (Basic Implementation)
```python
# Sync View (WSGI)
def sync_view(request):
    # Very fast, minimal overhead
    user = User.objects.get(id=1) 
    return JsonResponse({'name': user.name})

# Async View (ASGI with psycopg2)
async def async_view(request):
    # Slower! Incurs thread pool boundary overhead
    user = await User.objects.aget(id=1)
    return JsonResponse({'name': user.name})
```

## 5. Production-Ready Optimization
If you must mix sync and async, isolate them at the routing level.
Use separate deployments:
1. `api.example.com` (WSGI + Gunicorn, 90% of traffic, pure CRUD)
2. `ws.example.com` (ASGI + Uvicorn, 10% of traffic, WebSockets, SSE, async fan-out)

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:** Using async purely because it "looks modern". Rewriting a mature, highly optimized WSGI Django app into ASGI just to use `aget()` will result in degraded performance and massive bug surfaces.

## 7. Environment-Specific Behavior
| Setup | Simple DB Query | Multiple External API Calls |
|-------|-----------------|-----------------------------|
| Django WSGI | **Fastest** | Very Slow (Blocks workers) |
| Django ASGI (psycopg2) | Slowest (Thread overhead) | **Fastest** (Concurrent I/O) |
| Django ASGI (psycopg3) | Fast (Near WSGI) | **Fastest** (Concurrent I/O) |

## 8. Local Development Issues
🔴 SYMPTOM: Unit tests are significantly slower after adding ASGI.
🔍 CAUSE: `asgiref` test clients and async test cases have heavy setup/teardown overhead compared to standard Django `TestCase`.
🔧 FIX: Keep tests synchronous where possible, use `@pytest.mark.asyncio` sparingly.

## 9. Production Issues
🚨 INCIDENT: High Memory Usage on ASGI Workers
- **Investigation:** Uvicorn workers were consuming 3x the memory of old Gunicorn WSGI workers. The app was using async views, triggering the `sync_to_async` thread pool extensively. The combination of event loop memory + thread pool memory per worker bloated RAM.
- **Fix:** Reduced `ASGI_THREADS`. Migrated heavy sync dependencies to native async alternatives where possible.

## 10. Failure Simulation
Run a load test (`wrk` or `locust`) against a basic `User.objects.all()` JSON endpoint on both WSGI and ASGI (with psycopg2). You will see WSGI handles more Requests Per Second (RPS) with lower latency.

## 11. Decision Matrix
- **When Async HURTS:** High CPU usage (math, ML, image processing), basic DB CRUD apps, systems heavily reliant on legacy sync libraries (boto3, older SQLAlchemy).
- **When Async SHINES:** Chat apps, WebSockets, Long-polling, API gateways aggregating 5+ microservices per request, SSE (Server-Sent Events).

## 12. Senior-Level Questions
**Q:** How do I handle AWS SDK (boto3) in Django ASGI? It's synchronous!
**A:** You have two choices: wrap `boto3` calls in `sync_to_async(thread_sensitive=False)`, or migrate to `aioboto3` which natively supports `asyncio`. The latter is much better for scalability.

## 13. Production Checklist
- [ ] Load tested WSGI vs ASGI for your specific workloads.
- [ ] Identified genuinely I/O bound endpoints to justify async.
- [ ] Ensured PostgreSQL uses psycopg3 if moving fully to ASGI.
