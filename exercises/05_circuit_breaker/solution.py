import time
from enum import Enum
from typing import Callable, Any

class State(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreakerOpenException(Exception):
    pass

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 5, fallback_func: Callable = None):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.fallback_func = fallback_func
        
        self.state = State.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        
    def __call__(self, func: Callable, *args, **kwargs) -> Any:
        self._check_state()
        
        if self.state == State.OPEN:
            if self.fallback_func:
                return self.fallback_func(*args, **kwargs)
            raise CircuitBreakerOpenException("Circuit is OPEN")
            
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            if isinstance(e, CircuitBreakerOpenException):
                raise
            self._on_failure()
            if self.fallback_func:
                return self.fallback_func(*args, **kwargs)
            raise e
            
    def _check_state(self):
        if self.state == State.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = State.HALF_OPEN
                
    def _on_success(self):
        self.failure_count = 0
        self.state = State.CLOSED
        
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == State.HALF_OPEN or self.failure_count >= self.failure_threshold:
            self.state = State.OPEN
