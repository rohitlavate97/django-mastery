# Exercise 05: Circuit Breaker Pattern

## Objective
Implement a stateful Circuit Breaker to protect your system from cascading failures when a third-party API goes down.

## Context
When a third-party API is experiencing a partial outage or severe latency, repeatedly calling it can exhaust your application's connection pools and threads. A Circuit Breaker acts like an electrical circuit breaker:
- **CLOSED**: Traffic flows normally. If failures exceed a threshold, it trips to OPEN.
- **OPEN**: Traffic is blocked immediately (fail-fast) without attempting to call the failing service. A fallback response can be provided. After a timeout, it transitions to HALF_OPEN.
- **HALF_OPEN**: Allows a single test request through. If it succeeds, the circuit closes (recovers). If it fails, the circuit opens again.

## Requirements
Implement the `CircuitBreaker` class in `solution.py`.
1. It should wrap a callable function.
2. It should have `failure_threshold` (e.g., 3 failures trips the circuit) and `recovery_timeout` (e.g., 5 seconds before trying again).
3. Provide a fallback function mechanism.
4. Implement the three states correctly (`CLOSED`, `OPEN`, `HALF_OPEN`).

## Hints
- You can use a state machine approach or simple state variables.
- Track the number of consecutive failures.
- Track the timestamp of when the circuit was tripped.
