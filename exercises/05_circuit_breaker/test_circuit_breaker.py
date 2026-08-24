import pytest
import time
from .solution import CircuitBreaker, CircuitBreakerOpenException, State

def failing_api():
    raise ConnectionError("API is down")

def successful_api():
    return "OK"

def fallback():
    return "Fallback Response"

def test_circuit_breaker_trips_on_threshold():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
    
    # First failure
    with pytest.raises(ConnectionError):
        cb(failing_api)
    assert cb.state == State.CLOSED
    
    # Second failure (trips threshold)
    with pytest.raises(ConnectionError):
        cb(failing_api)
    assert cb.state == State.OPEN
    
    # Third call should fail fast without running the API
    with pytest.raises(CircuitBreakerOpenException):
        cb(failing_api)
        
def test_circuit_breaker_fallback():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1, fallback_func=fallback)
    
    # First failure trips circuit and returns fallback
    assert cb(failing_api) == "Fallback Response"
    assert cb.state == State.OPEN
    
    # Second call uses fallback directly
    assert cb(failing_api) == "Fallback Response"

def test_circuit_breaker_recovery():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
    
    # Trip the circuit
    with pytest.raises(ConnectionError):
        cb(failing_api)
    assert cb.state == State.OPEN
    
    # Wait for recovery timeout
    time.sleep(1.1)
    
    # The next call should be allowed through (HALF_OPEN)
    # Let's mock a successful api response
    assert cb(successful_api) == "OK"
    
    # State should now be closed again
    assert cb.state == State.CLOSED
    
def test_circuit_breaker_half_open_failure():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
    
    with pytest.raises(ConnectionError):
        cb(failing_api)
        
    time.sleep(1.1)
    
    # During HALF_OPEN, if it fails, it should immediately trip back to OPEN
    with pytest.raises(ConnectionError):
        cb(failing_api)
        
    assert cb.state == State.OPEN
    
    with pytest.raises(CircuitBreakerOpenException):
        cb(successful_api)  # Even a successful call is blocked now
