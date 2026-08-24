import hmac
import hashlib
import time
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
from django.contrib.auth.models import User

class HMACAuthentication(BaseAuthentication):
    """
    Authenticates requests based on an HMAC SHA-256 signature.
    Requires headers: X-Signature, X-Timestamp
    """
    def authenticate(self, request):
        signature = request.headers.get('X-Signature')
        timestamp_str = request.headers.get('X-Timestamp')
        
        if not signature or not timestamp_str:
            return None # Move to next auth class or fail
            
        try:
            timestamp = float(timestamp_str)
        except ValueError:
            raise AuthenticationFailed('Invalid timestamp format.')
            
        # Replay protection: max 5 minutes (300 seconds)
        current_time = time.time()
        if abs(current_time - timestamp) > 300:
            raise AuthenticationFailed('Request timestamp expired.')
            
        # Secret key (in real app, might be looked up by an API key ID)
        secret = getattr(settings, 'HMAC_SECRET', 'default-secret-key').encode('utf-8')
        
        # Request body
        body = request.body if hasattr(request, 'body') else b''
        
        # Message to sign
        message = str(timestamp).encode('utf-8') + body
        
        # Calculate expected signature
        expected_signature = hmac.new(
            secret,
            message,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(expected_signature, signature):
            raise AuthenticationFailed('Invalid signature.')
            
        # Return a dummy user for the purpose of the exercise
        user = User(username='api_user')
        return (user, None)
