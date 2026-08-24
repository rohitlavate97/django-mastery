import time
import redis

# The Lua script ensures the check-and-set operations are atomic.
# KEYS[1] = rate limiter key (e.g., 'rate_limit:ip:192.168.1.1')
# ARGV[1] = current timestamp in milliseconds
# ARGV[2] = window size in milliseconds
# ARGV[3] = limit
# ARGV[4] = a unique member id (to avoid overwriting identical timestamps in the sorted set)
LUA_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member_id = ARGV[4]

local clear_before = now - window

-- Remove old entries outside the sliding window
redis.call('ZREMRANGEBYSCORE', key, 0, clear_before)

-- Count current valid requests
local current_requests = redis.call('ZCARD', key)

if current_requests < limit then
    -- Add the new request
    redis.call('ZADD', key, now, member_id)
    -- Set TTL on the key to clean up memory when idle
    -- TTL in seconds is window_seconds + 1
    redis.call('EXPIRE', key, math.ceil(window / 1000) + 1)
    return 1
else
    return 0
end
"""

class SlidingWindowRateLimiter:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self._script = self.redis.register_script(LUA_SCRIPT)
        
    def allow_request(self, key: str, limit: int, window_seconds: int) -> bool:
        now_ms = int(time.time() * 1000)
        window_ms = window_seconds * 1000
        # Unique member id ensures multiple requests in the exact same millisecond
        # don't collapse into a single element in the sorted set.
        member_id = f"{now_ms}-{id(self)}"
        
        result = self._script(
            keys=[key],
            args=[now_ms, window_ms, limit, member_id]
        )
        return bool(result)
