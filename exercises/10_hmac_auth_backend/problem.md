# Exercise 10: HMAC Signature Authentication

## The Problem
For API-to-API communication (e.g., webhooks or microservices), sending API keys in headers can be risky if intercepted. A more secure method is HMAC SHA-256 signature authentication, where the client signs the request body and a timestamp using a shared secret. The server verifies the signature to ensure authenticity and integrity, and checks the timestamp to prevent replay attacks.

## Your Task
Implement a custom Django REST Framework (DRF) authentication backend that validates an HMAC signature.

### Requirements
1. **Headers**: The client sends `X-Signature` (hex digest) and `X-Timestamp` (unix epoch).
2. **Signature Logic**: Calculate HMAC SHA-256 using the shared secret, the request body, and the timestamp. `signature = hmac(secret, timestamp + body)`.
3. **Replay Protection**: Reject requests where the timestamp is more than 300 seconds old.
4. **Authentication**: Inherit from `BaseAuthentication` and implement `authenticate(self, request)`. Raise `AuthenticationFailed` for invalid signatures, expired timestamps, or missing headers.
