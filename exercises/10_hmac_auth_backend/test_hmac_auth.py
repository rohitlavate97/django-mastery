import pytest
import hmac
import hashlib
import time
import json
from unittest.mock import Mock
from rest_framework.exceptions import AuthenticationFailed
from .solution import HMACAuthentication

def test_hmac_authentication_success(settings):
    settings.HMAC_SECRET = 'my-secret'
    auth = HMACAuthentication()
    
    timestamp = time.time()
    body = b'{"data": "test"}'
    
    message = str(timestamp).encode('utf-8') + body
    signature = hmac.new(b'my-secret', message, hashlib.sha256).hexdigest()
    
    request = Mock()
    request.headers = {'X-Signature': signature, 'X-Timestamp': str(timestamp)}
    request.body = body
    
    user, auth_context = auth.authenticate(request)
    assert user.username == 'api_user'

def test_hmac_authentication_expired(settings):
    settings.HMAC_SECRET = 'my-secret'
    auth = HMACAuthentication()
    
    timestamp = time.time() - 400 # 400 seconds ago, > 300 threshold
    body = b'{"data": "test"}'
    
    message = str(timestamp).encode('utf-8') + body
    signature = hmac.new(b'my-secret', message, hashlib.sha256).hexdigest()
    
    request = Mock()
    request.headers = {'X-Signature': signature, 'X-Timestamp': str(timestamp)}
    request.body = body
    
    with pytest.raises(AuthenticationFailed, match="Request timestamp expired"):
        auth.authenticate(request)

def test_hmac_authentication_invalid_signature(settings):
    settings.HMAC_SECRET = 'my-secret'
    auth = HMACAuthentication()
    
    timestamp = time.time()
    body = b'{"data": "test"}'
    
    request = Mock()
    request.headers = {'X-Signature': 'invalid-sig', 'X-Timestamp': str(timestamp)}
    request.body = body
    
    with pytest.raises(AuthenticationFailed, match="Invalid signature"):
        auth.authenticate(request)
