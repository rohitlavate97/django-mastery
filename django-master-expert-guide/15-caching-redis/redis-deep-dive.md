# Redis Deep Dive for Django

## 1. Mental Model
```text
Django Application
      |
      | (Pickled/JSON Data)
      v
+-----------------------------+
|        Redis Server         |
|  [Keyspace 0]               |
|  - cache:user:1 (String)    |
|  - cache:sessions (Hash)    |
|  - celery:queue (List)      |
+-----------------------------+
```

## 2. Why It Exists
Relational databases are optimized for persistent, structured data, but they are too slow for high-frequency reads (like session data or rendered HTML fragments). Redis operates entirely in memory, offering sub-millisecond response times, making it the perfect caching and message broker layer for Django.

## 3. Internal Working
When Django calls `cache.set('key', 'value')`, the `django-redis` backend serializes the Python object (usually using Pickle) and sends a `SET key value EX timeout` command to Redis over a socket connection. 

## 4. Basic Implementation
`settings.py`:
```python
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}
```

## 5. Production-Ready Implementation
Production Redis configurations require connection pooling, strict serialization, and timeout management.

```python
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 100,
                "retry_on_timeout": True,
            },
            # Prefer JSON over Pickle for security (requires custom serializer or setup)
            # "SERIALIZER": "django_redis.serializers.json.JSONSerializer", 
        }
    }
}
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:**
```python
# Using keys() in production
keys = cache.keys('*user*')
for key in keys:
    cache.delete(key)
```
*Why it's bad:* The `KEYS` command blocks the entire Redis single-threaded event loop. In production with millions of keys, this will cause a massive latency spike and potentially take down your app. Always use `SCAN` or pattern-based deletion via `django-redis` `delete_pattern`.

## 7. Environment-Specific Behavior
| Config | Local | Production |
|--------|-------|------------|
| Connection | Single | Pooled (`max_connections`) |
| Persistence | RDB/AOF off | RDB + AOF enabled |
| High Availability | Standalone | Sentinel / Cluster |

## 8. Local Development Issues
🔴 SYMPTOM: `redis.exceptions.ConnectionError: Error 61 connecting to 127.0.0.1:6379. Connection refused.`
🔍 CAUSE: Redis server is not running locally.
🔧 FIX: Start Redis (`brew services start redis` on Mac, or run a Docker container: `docker run -p 6379:6379 redis`).

## 9. Production Issues
🔴 INCIDENT: Cache Stampede (Thundering Herd)
- **Severity:** HIGH
- **Investigation:** Database CPU spiked to 100% every hour on the dot.
- **Root Cause:** A highly accessed, expensive query result cached for exactly 1 hour expired. Thousands of concurrent requests hit the cache miss simultaneously, sending identical queries to the database.
- **Fix:** Implemented a lock (mutex) for the cache regeneration, or used a stale-while-revalidate pattern (regenerating cache in a background Celery task before it expires).

## 10. Failure Simulation
Stop your local Redis instance (`docker stop redis`) and observe your Django application. Does it crash completely, or gracefully fall back to database reads? (Hint: default Django cache throws exceptions. You need to configure a fallback or catch exceptions).

## 11. Decision Matrix
| Policy | Behavior | When to Use |
|--------|----------|-------------|
| `allkeys-lru` | Evicts least recently used keys | Standard caching workloads |
| `volatile-ttl` | Evicts keys with the shortest TTL | When mixing cache and persistent data (e.g., Celery queues) |
| `noeviction` | Returns errors when memory full | Strict data integrity needed |

## 12. Senior-Level Questions
**Q: Pickle is the default serializer in `django-redis`. Why is this a security risk, and how do you mitigate it?**
A: Pickle can execute arbitrary code during deserialization. If an attacker gains access to your Redis instance and injects a malicious pickled payload, they achieve Remote Code Execution (RCE) on your Django servers. Mitigation: Secure Redis with authentication/VPCs, or switch to a JSON/MsgPack serializer for the cache.

## 13. Production Checklist
- [ ] Redis memory eviction policy is set (usually `allkeys-lru` for caches).
- [ ] Connection pooling is configured in Django.
- [ ] Redis is secured (not exposed to the public internet, password protected).
