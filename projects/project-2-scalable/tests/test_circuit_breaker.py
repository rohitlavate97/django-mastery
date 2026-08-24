import pytest
import pybreaker
from apps.integrations.clients import ExternalClient, breaker

def test_circuit_breaker_opens_on_failures(monkeypatch):
    def mock_call(*args, **kwargs):
        raise ValueError("Simulated failure")
        
    monkeypatch.setattr("httpx.post", mock_call)
    
    breaker.close()
    for _ in range(3):
        with pytest.raises(Exception):
            ExternalClient.call_payment_gateway({})
            
    assert breaker.current_state == 'open'
