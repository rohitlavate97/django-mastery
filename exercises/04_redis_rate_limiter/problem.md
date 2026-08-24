# Exercise 04: Redis Rate Limiter

## Objective
Implement a distributed sliding window log rate limiter using Redis and Lua scripting to guarantee atomicity.

## Context
A fixed-window rate limiter is easy to implement (e.g., using Redis `INCR` and `EXPIRE`), but it suffers from the "burst at the edges" problem, allowing up to 2x the limit at window boundaries. A sliding window log algorithm solves this.

## Requirements
Implement the `SlidingWindowRateLimiter` class in `solution.py` with an `allow_request(key, limit, window_seconds)` method.
1. It must use Redis as the backend.
2. It must use a Lua script for atomicity (so multiple concurrent checks for the same key don't cause race conditions).
3. The algorithm:
   - Remove timestamps older than `current_time - window_seconds`.
   - Count the number of remaining timestamps.
   - If count < `limit`, add the `current_time` and return `True`.
   - Else, return `False`.
   - Ensure the Redis key has a TTL (expiration) so we don't leak memory.

## Hints
- Use Redis sorted sets (`ZADD`, `ZREMRANGEBYSCORE`, `ZCARD`).
- The score should be the timestamp (in milliseconds for better precision).
- Pass the current time as an argument to the Lua script, since Lua script execution shouldn't depend on system time inside Redis (though `redis.call('TIME')` is allowed in newer Redis).
