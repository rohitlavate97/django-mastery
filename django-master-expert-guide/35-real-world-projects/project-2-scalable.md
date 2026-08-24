# Blueprint: Project 2 - Scalable (High-Throughput API)

## Mental Model
Once you move past the "Foundation" stage, the database becomes your bottleneck. Scaling a Django application means systematically offloading work from the primary PostgreSQL database to Redis (caching) and Celery (asynchronous processing), while instrumenting everything so you can see where time is spent.

```text
                                       +--> [ Redis Cache ]
                                       |
[ Request ] -> [ Load Balancer ] -> [ Web Workers ] ---> [ PostgreSQL Primary ] -> [ Read Replicas ]
                                       |
                                       +--> [ Redis Broker ] -> [ Celery Workers ]
```

## 1. Advanced Caching Strategies

### The Trap of `cache_page`
Using Django's `@cache_page` decorator caches the *entire* HTML/JSON response. If a logged-in user requests the page, you might accidentally cache their PII and serve it to the next user.

### Production Implementation: Cache-Aside Pattern
Cache the expensive *data*, not the HTTP response.

```python
# services/leaderboard.py
from django.core.cache import cache
from .models import UserStats

def get_top_users():
    # 1. Try to fetch from cache
    cache_key = "leaderboard:top_100"
    data = cache.get(cache_key)

    if data is None:
        # 2. Cache miss: execute expensive DB query
        data = list(
            UserStats.objects.select_related('user')
            .order_by('-score')[:100]
            .values('user__username', 'score')
        )
        # 3. Store in cache for 5 minutes
        cache.set(cache_key, data, timeout=300)
    
    return data
```

### Cache Invalidation (The Hard Part)
When a user scores points, the leaderboard cache becomes stale.
```python
# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache
from .models import UserStats

@receiver(post_save, sender=UserStats)
def invalidate_leaderboard(sender, instance, **kwargs):
    # Only invalidate if score changed (requires tracking old state)
    cache.delete("leaderboard:top_100")
```

## 2. Background Processing with Celery

### Handling High-Volume Webhooks
If a third-party service (like Stripe) sends a webhook, acknowledge it immediately (200 OK) and process it in the background. If you process it synchronously and timeout, Stripe will keep retrying and DDOS your application.

```python
# views.py
import json
from django.http import HttpResponse
from .tasks import process_stripe_webhook

def stripe_webhook_view(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    # 1. Verify signature synchronously (fast)
    event = verify_stripe_signature(payload, sig_header)
    if not event:
        return HttpResponse(status=400)
        
    # 2. Send to Celery (async)
    process_stripe_webhook.delay(event.id, json.loads(payload))
    
    # 3. Return 200 immediately
    return HttpResponse(status=200)
```

### Celery Production Config
```python
# settings.py
CELERY_BROKER_URL = env('REDIS_URL')
CELERY_RESULT_BACKEND = env('REDIS_URL')
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # Kill task if it runs > 30 mins
CELERY_TASK_SOFT_TIME_LIMIT = 29 * 60 # Raise SoftTimeLimitExceeded exception
CELERY_WORKER_PREFETCH_MULTIPLIER = 1 # Fair distribution for long tasks
```

## 3. Observability with Prometheus

You cannot optimize what you cannot measure. Use `django-prometheus` to expose metrics.

```python
# settings.py
INSTALLED_APPS = [
    ...
    'django_prometheus',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    ... # Other middleware
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]
```

### Creating Custom Metrics
```python
from prometheus_client import Counter

PAYMENT_PROCESSED_COUNTER = Counter(
    'payments_processed_total', 
    'Total payments processed',
    ['status'] # Labels
)

def process_payment():
    try:
        # logic
        PAYMENT_PROCESSED_COUNTER.labels(status='success').inc()
    except Exception:
        PAYMENT_PROCESSED_COUNTER.labels(status='failure').inc()
```

## 4. Load Testing with Locust

Before going live, simulate 500 concurrent users.

```python
# locustfile.py
from locust import HttpUser, task, between

class APIUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Login and get JWT token
        response = self.client.post("/api/login/", json={
            "email": "test@example.com",
            "password": "password123"
        })
        self.token = response.json().get("access")

    @task(3)
    def view_leaderboard(self):
        self.client.get("/api/leaderboard/", headers={"Authorization": f"Bearer {self.token}"})

    @task(1)
    def submit_score(self):
        self.client.post("/api/scores/", json={"score": 500}, headers={"Authorization": f"Bearer {self.token}"})
```
