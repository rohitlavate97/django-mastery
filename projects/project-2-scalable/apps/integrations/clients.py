import pybreaker
import httpx

breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=30)

class ExternalClient:
    @staticmethod
    @breaker
    def call_payment_gateway(data):
        response = httpx.post("https://httpbin.org/delay/2", json=data)
        response.raise_for_status()
        return response.json()
