# JWT Deep Dive in Django

## 1. Mental Model
```text
Header (Algorithm) . Payload (Claims: user_id, exp) . Signature (HMAC-SHA256)
eyJhbGciOiJIUzI1NiJ9 . eyJ1c2VyX2lkIjoxLCJleHAiOjE2MTAwMDAwMDB9 . SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
```

## 2. Why It Exists
To provide stateless authentication, usually for SPAs, Mobile Apps, or microservices, avoiding database lookups for session IDs on every API request.

## 3. Internal Working
Uses `django-rest-framework-simplejwt`. The server signs the payload with `SECRET_KEY`. When the client sends the token in the `Authorization: Bearer <token>` header, the server verifies the signature computationally—no DB hit required.

## 4. Basic Implementation vs 5. Production-Ready Implementation

### Basic 🟡
Storing tokens in `localStorage`. This is vulnerable to XSS attacks, allowing malicious scripts to steal the token.

### Production-Ready 🟢
Store JWTs in `HttpOnly` cookies.
```python
# settings.py
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# Custom view to set tokens in HttpOnly cookies
from rest_framework_simplejwt.views import TokenObtainPairView
from django.conf import settings

class CookieTokenObtainPairView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            access_token = response.data.get('access')
            refresh_token = response.data.get('refresh')
            
            response.set_cookie(
                'access_token', access_token,
                max_age=settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds(),
                httponly=True, samesite='Lax', secure=settings.SESSION_COOKIE_SECURE
            )
            response.set_cookie(
                'refresh_token', refresh_token,
                max_age=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds(),
                httponly=True, samesite='Lax', secure=settings.SESSION_COOKIE_SECURE
            )
            # Remove from response body to force cookie usage
            del response.data['access']
            del response.data['refresh']
        return response
```

## 6. Anti-Patterns
🔴 **Anti-Pattern:** Long-lived Access Tokens (e.g., 30 days).
*Why it's bad:* Since JWTs are stateless, they cannot be easily revoked before expiration. If stolen, the attacker has access for 30 days.

## 7. Environment-Specific Behavior
| Environment | Behavior |
|-------------|----------|
| SPA/Next.js | Needs careful handling of CORS and credentials (`withCredentials=true`) to pass cookies. |

## 8. Local Development Issues
🔴 SYMPTOM: Tokens are not sent with requests.
🔍 CAUSE: Using Cookies but Axios/Fetch is not configured to send credentials.
🔧 FIX: `axios.defaults.withCredentials = true;`

## 9. Production Issues
🔴 INCIDENT: **Stolen Refresh Token**
- **Severity:** High
- **Investigation:** An attacker exfiltrated a refresh token and continuously minted new access tokens.
- **Root Cause:** `ROTATE_REFRESH_TOKENS` was False.
- **Fix:** Enable `ROTATE_REFRESH_TOKENS` and `BLACKLIST_AFTER_ROTATION`. When a refresh token is used, issue a new one and blacklist the old one. If the old one is used again, invalidate the entire chain!

## 10. Failure Simulation
Change the server's `SECRET_KEY`. All existing JWTs will fail signature validation immediately.

## 11. Decision Matrix
| Storage | XSS Safe? | CSRF Safe? | Verdict |
|---------|-----------|------------|---------|
| localStorage | No | Yes | Avoid for sensitive apps |
| HttpOnly Cookie | Yes | No | **Best**, but requires CSRF tokens |

## 12. Senior-Level Questions
**Q:** If JWTs are stateless, how do we instantly revoke a user's access?
**A:** True stateless JWTs cannot be revoked. You must either keep access tokens extremely short-lived (e.g., 5 mins) or introduce a DB check (like a "token version" or blacklisted JTI list) per request, which defeats the point of statelessness.

## 13. Production Checklist
- [ ] Access token lifetime < 15 minutes.
- [ ] Refresh token rotation enabled.
- [ ] Blacklist app installed (`rest_framework_simplejwt.token_blacklist`).
- [ ] Tokens stored in `HttpOnly` cookies for browser clients.
