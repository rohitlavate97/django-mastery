# Authentication Backends in DRF

## 1. Mental Model

Authentication answers "Who are you?", Permissions answer "Can you do this?".

```text
Request (Headers/Cookies)
      |
      v
DRF Authentication Classes (iterated sequentially)
      |
      |-- 1. SessionAuthentication (Checks cookies, strictly requires CSRF)
      |-- 2. TokenAuthentication (Checks Authorization: Token xyz)
      |-- 3. JWTAuthentication (Checks Authorization: Bearer <jwt>)
      |
      v
Populates `request.user` and `request.auth` (Lazy Evaluation)
```

## 2. Session Authentication & CSRF
If you use `SessionAuthentication` in DRF, it strictly enforces CSRF checks for unsafe methods (POST, PUT, DELETE, PATCH). This is unlike standard Django views marked with `@csrf_exempt`.

## 3. JWT vs TokenAuthentication

### 🔴 Standard `TokenAuthentication` (Ticking Time Bomb)
Tokens never expire. If a token is leaked, it is valid forever until manually deleted from the DB. Causes DB hits on every request.

### 🟢 `djangorestframework-simplejwt`
Stateless (no DB hits), short-lived access tokens, long-lived refresh tokens.

```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    )
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True, # Requires DB for blacklist
}
```

## 4. Custom Header Authentication (Production Grade)

Sometimes you need API Key auth for machine-to-machine communication.

```python
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.core.cache import cache
from .models import APIKey

class APIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request):
        api_key = request.META.get('HTTP_X_API_KEY')
        if not api_key:
            return None # Move to next auth backend
            
        # Cache check for performance
        user_id = cache.get(f'apikey_user_{api_key}')
        
        if not user_id:
            try:
                key_obj = APIKey.objects.select_related('user').get(key=api_key, is_active=True)
                user = key_obj.user
                cache.set(f'apikey_user_{api_key}', user.id, timeout=300)
            except APIKey.DoesNotExist:
                raise AuthenticationFailed('Invalid API Key')
        else:
            from django.contrib.auth import get_user_model
            user = get_user_model().objects.get(id=user_id)
            
        return (user, api_key)
```

## 5. Lazy Evaluation
DRF evaluates `request.user` lazily. If a view has `permission_classes = [AllowAny]`, the authentication backends are NEVER called, saving DB/Cache hits!

## 6. Production Checklist
- [ ] Stateless authentication (JWT) preferred over DB-backed tokens for high scale.
- [ ] Hardcoded long-lived tokens strictly avoided.
- [ ] API keys are hashed in the database, never stored in plain text.
