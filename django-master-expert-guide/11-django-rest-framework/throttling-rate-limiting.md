# Throttling and Rate Limiting

## 1. Mental Model

```text
Request
  |
  v
Throttle Classes `allow_request()`
  |-- Check Cache (Redis) for IP or User ID rate limit counters
  |-- If threshold exceeded -> raise Throttled (HTTP 429)
  v
View Execution
```

## 2. DRF Built-in Throttles

- **AnonRateThrottle**: Limits based on IP address. Uses `DEFAULT_THROTTLE_RATES['anon']`.
- **UserRateThrottle**: Limits based on authenticated user ID. Uses `DEFAULT_THROTTLE_RATES['user']`.
- **ScopedRateThrottle**: Limits based on specific view strings.

## 3. Redis-Backed Production Implementation

Always use a fast in-memory store (Redis/Memcached) for throttling. Database-backed cache for throttling will crush your DB under a DDoS attack.

```python
# settings.py
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
    }
}

REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/hour',
        'burst': '10/minute',
        'sustained': '10000/day'
    }
}
```

## 4. Custom Tier-Based Throttling

```python
from rest_framework.throttling import UserRateThrottle

class TieredUserRateThrottle(UserRateThrottle):
    """
    Dynamic rate limiting based on user subscription tier.
    """
    def get_rate(self):
        user = self.request.user
        if not user.is_authenticated:
            return None
            
        if user.tier == 'premium':
            return '10000/hour'
        elif user.tier == 'basic':
            return '1000/hour'
        return '100/hour' # free tier
```

## 5. Burst vs Sustained

To protect your API, apply multiple throttles:
1. Prevent instant spikes: `BurstThrottle (10/sec)`
2. Prevent daily scraping: `SustainedThrottle (10000/day)`

Apply both to the view.

## 6. Incident Report: Cache Stampede & Lockup
**Severity**: High
**Symptom**: Redis CPU hit 100%, API latency skyrocketed.
**Cause**: Used DB cache backend for throttling instead of Redis. When bots hit the API, DB maxed out connections trying to increment throttle counters.
**Fix**: Moved cache backend to Redis and used `django-redis` with connection pooling.

## 7. Production Checklist
- [ ] Throttling backend is configured to use Redis/Memcached.
- [ ] Both Burst and Sustained throttles are implemented on expensive endpoints (e.g., Reports, Export).
- [ ] Anonymous endpoints (Login, Signup, Password Reset) have extremely strict IP rate limits.
