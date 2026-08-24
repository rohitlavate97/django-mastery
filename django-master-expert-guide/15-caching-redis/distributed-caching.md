# Distributed Caching in Django

## 1. Mental Model
```text
[Django App 1] \         +-> [Redis Master] (Writes)
[Django App 2]  > Proxy -|
[Django App 3] /         +-> [Redis Replica 1] (Reads)
                         +-> [Redis Replica 2] (Reads)

Distributed Architectures:
1. Master-Replica (Scaling Reads)
2. Redis Sentinel (High Availability/Failover)
3. Redis Cluster (Horizontal Scaling / Sharding)
```

## 2. Why It Exists
A single Redis instance is bound by the memory and CPU of one machine (Redis is single-threaded). When your cache dataset exceeds available RAM, or your throughput exceeds what one thread can handle, you must distribute the cache across multiple nodes.

## 3. Internal Working
- **Sentinel:** Monitors a Master-Replica setup. If the Master dies, Sentinel promotes a Replica to Master and updates Django's routing.
- **Cluster:** Shards data across multiple nodes. Key `user:1` might live on Node A, while `user:2` lives on Node B. The client (`django-redis`) must know how to route the request based on a hash of the key.

## 4. Basic Implementation (Master/Replica with django-redis)
`django-redis` supports configuring separate nodes for read and write operations.

```python
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": [
            "redis://master-node:6379/1",   # Index 0 is always the Master (writes)
            "redis://replica-node-1:6379/1", # Subsequent are Replicas (reads)
            "redis://replica-node-2:6379/1",
        ],
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            # Enable connection pooling
            "CONNECTION_POOL_KWARGS": {"max_connections": 100},
        }
    }
}
```

## 5. Production-Ready Implementation (Redis Sentinel)
In a true high-availability setup, you don't point Django to specific IPs (which can change during failover). You point Django to the Sentinels.

```python
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://sentinel-node-1:26379/mymaster,redis://sentinel-node-2:26379/mymaster",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.SentinelClient", # Note the different client
            "SENTINEL_KWARGS": {"password": "secret_password"},
            "CONNECTION_POOL_KWARGS": {"max_connections": 100},
        }
    }
}
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:**
```python
# Assuming transactions work across a Redis Cluster
with cache.client.pipeline() as pipe:
    pipe.set("user:1:name", "Alice")
    pipe.set("user:2:name", "Bob")
    pipe.execute()
```
*Why it's bad:* In a Redis Cluster, `user:1` and `user:2` likely hash to different physical nodes (shards). Multi-key operations (like pipelines or transactions) will throw a `CROSSSLOT` error because Redis cannot guarantee atomicity across different servers. You must use "Hash Tags" (e.g., `{users}:1` and `{users}:2`) to force them onto the same node.

## 7. Environment-Specific Behavior
| Feature | Local | Staging | Production |
|---------|-------|---------|------------|
| Topology| Standalone | Standalone | Sentinel or Cluster |
| Failover| Manual | Manual | Automatic via Sentinel |

## 8. Local Development Issues
🔴 SYMPTOM: You configure Sentinel locally in Docker, but Django fails to connect to the promoted master.
🔍 CAUSE: Docker networking. Sentinel reports the internal container IP of the Master (e.g., `172.18.0.2`), which your host Django app cannot route to.
🔧 FIX: Run Django inside the same Docker network, or configure Sentinel to announce host-mappable IPs via `sentinel announce-ip`.

## 9. Production Issues
🔴 INCIDENT: Split-Brain Data Corruption
- **Severity:** HIGH
- **Investigation:** During a network partition, some Django nodes wrote to the old Master, while others wrote to the newly promoted Master. When the network resolved, the old Master was demoted to a replica and its data was overwritten.
- **Root Cause:** A misconfigured Sentinel quorum (too few nodes required to agree on a failover).
- **Fix:** Ensured an odd number of Sentinel nodes (minimum 3) and required a quorum of 2 for failovers.

## 10. Failure Simulation
Setup a Master-Replica locally with Docker. Run a Django script that continuously reads from the cache. Manually kill the Master container. If using standard Master-Replica, Django will fail on writes but reads might survive. If using Sentinel, observe the brief downtime (failover window) before reads/writes resume automatically.

## 11. Decision Matrix
| Architecture | Pros | Cons | Use Case |
|--------------|------|------|----------|
| Standalone | Simple, fast | Single point of failure | Dev / Small apps |
| Sentinel | High Availability | No write scaling | Med/Large apps needing HA |
| Cluster | Scales writes/memory | High complexity, no multi-key ops | Enterprise scale |

## 12. Senior-Level Questions
**Q: How does `django-redis` handle the `mget` (multi-get) command in a Redis Cluster?**
A: Because keys might live on different nodes, `django-redis` (via the underlying `redis-py-cluster` library) must intercept the `mget`, split the keys based on their hash slots, query the respective nodes in parallel, and reassemble the results before returning them to Django. This adds network overhead compared to a standalone instance.

## 13. Production Checklist
- [ ] Sentinel or Cluster is used for HA; Standalone is strictly forbidden in Prod.
- [ ] Connection pooling is enabled to prevent socket exhaustion.
- [ ] Multi-key operations (`MSET`, `MGET`, Pipelines) use Hash Tags to ensure slot alignment.
- [ ] `django-redis` client is configured correctly for the chosen topology (`DefaultClient` vs `SentinelClient`).
