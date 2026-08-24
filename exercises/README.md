# Django Mastery Hands-On Exercises

Welcome to the Django Mastery coding exercises! This curriculum is designed to push your understanding of Python and Django internals to a senior/staff level.

## Prerequisites
- Python 3.12+
- Django 5.0+
- pytest & pytest-django
- redis (for rate limiter exercise)
- cryptography (for descriptors exercise)

## How to Run Tests
You can run the entire suite from the `exercises` directory:
```bash
pytest .
```

To run a specific exercise:
```bash
pytest 01_descriptors/
```

## Exercise Progression
1. **01_descriptors**: Deep dive into Python's descriptor protocol by building an `EncryptedFieldDescriptor`.
2. **02_orm_optimization**: Optimize severe N+1 queries using `select_related`, `prefetch_related`, and `annotate`.
3. **03_concurrency_race**: Solve a critical race condition in a multi-threaded balance transfer scenario using `select_for_update`.
4. **04_redis_rate_limiter**: Build a production-grade distributed sliding window rate limiter using Redis Lua scripts.
5. **05_circuit_breaker**: Implement a stateful Circuit Breaker pattern to protect against cascading third-party API failures.

## Grading & Solutions
Each exercise comes with a `problem.md` detailing the objectives, constraints, and hints.
The `test_*.py` files will validate your implementation.
The `solution.py` provides the canonical, production-ready solution.
