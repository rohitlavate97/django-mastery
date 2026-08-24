import pytest
import time
from .solution import SlidingWindowRateLimiter

# Normally we'd use fakeredis, but let's assume a real Redis or mock for the exercise.
# We will use fakeredis if available, otherwise skip if no local redis.
try:
    import fakeredis
    redis_available = True
    client = fakeredis.FakeRedis()
except ImportError:
    try:
        import redis
        client = redis.Redis(host='localhost', port=6379, db=0)
        client.ping()
        redis_available = True
    except:
        redis_available = False

@pytest.fixture
def rate_limiter():
    if not redis_available:
        pytest.skip("Redis or fakeredis not available")
    # Clear the fake/real db
    client.flushdb()
    return SlidingWindowRateLimiter(client)

def test_rate_limiter_allows_under_limit(rate_limiter):
    key = "user:123"
    limit = 3
    window = 1
    
    assert rate_limiter.allow_request(key, limit, window) is True
    assert rate_limiter.allow_request(key, limit, window) is True
    assert rate_limiter.allow_request(key, limit, window) is True
    
    # The 4th request should be rejected
    assert rate_limiter.allow_request(key, limit, window) is False

def test_rate_limiter_window_slides(rate_limiter):
    key = "user:456"
    limit = 2
    window = 1
    
    assert rate_limiter.allow_request(key, limit, window) is True
    assert rate_limiter.allow_request(key, limit, window) is True
    
    # 3rd is rejected
    assert rate_limiter.allow_request(key, limit, window) is False
    
    # Wait for the window to pass
    time.sleep(1.1)
    
    # Should be allowed again
    assert rate_limiter.allow_request(key, limit, window) is True
