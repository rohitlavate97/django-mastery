# OAuth 2.0 & OIDC in Django

## 1. Mental Model
```text
[ User ] -> Clicks "Login with Google"
  |
  v
[ Django (Client) ] -> Redirects to Google (Authorization Server)
  |
  v
[ Google ] -> User logs in, grants consent -> Redirects back with Auth Code
  |
  v
[ Django ] -> Exchanges Auth Code + Client Secret for Access Token & ID Token (OIDC)
  |
  v
[ Django ] -> Fetches user profile, creates/logs in local CustomUser
```

## 2. Why It Exists
Delegates authentication to external providers (Google, GitHub, Enterprise SSO). Reduces friction for users and shifts the burden of password security to the identity provider.

## 3. Internal Working
Using `django-allauth`: It handles the OAuth2 state parameter (CSRF protection), exchanges the code, and signals the creation of a `SocialAccount` linked to the Django `User`.

## 4. Basic Implementation vs 5. Production-Ready Implementation

### Basic 🟡
Using raw `requests` to handle the OAuth flow. Prone to state manipulation and security flaws.

### Production-Ready 🟢
```python
# settings.py using django-allauth
INSTALLED_APPS += [
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.github',
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'OAUTH_PKCE_ENABLED': True, # Crucial for security
    }
}

# Auto-link accounts by email
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
```

## 6. Anti-Patterns
🔴 **Anti-Pattern:** Not verifying the email address returned by the OAuth provider.
*Why it's bad:* Some providers (like GitHub) allow unverified emails in profiles. An attacker can create a GitHub account with a victim's email, log into your app, and hijack the victim's account. Always check `email_verified: true` in the OIDC claims.

## 7. Environment-Specific Behavior
| Environment | Behavior |
|-------------|----------|
| Local | Requires changing `/etc/hosts` or configuring authorized redirect URIs to `http://localhost:8000/accounts/google/login/callback/`. |
| Production | Redirect URIs must perfectly match, including trailing slashes and HTTPS. |

## 8. Local Development Issues
🔴 SYMPTOM: `redirect_uri_mismatch` from Google.
🔍 CAUSE: Google Developer Console authorized URI doesn't exactly match Django's local URI (e.g., `127.0.0.1` vs `localhost`).
🔧 FIX: Ensure the authorized redirect URI matches exactly, e.g., `http://localhost:8000/accounts/google/login/callback/`.

## 9. Production Issues
🔴 INCIDENT: **Account Hijacking via Social Login**
- **Severity:** Critical
- **Investigation:** User lost account access.
- **Root Cause:** A malicious user logged in via a provider where they registered the victim's email without verifying it. `django-allauth` auto-linked the account.
- **Fix:** Ensure `SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = False` OR only auto-link if the provider guarantees the email is verified.

## 10. Failure Simulation
Revoke the application's access from your Google Account settings. Try to log in again. Django should gracefully handle the re-authorization prompt.

## 11. Decision Matrix
| Auth Flow | Use Case |
|-----------|----------|
| Authorization Code | Standard Web Apps (Django rendering views) |
| Authorization Code + PKCE | Mobile Apps, SPAs (Next.js talking to Django DRF) |

## 12. Senior-Level Questions
**Q:** What is PKCE and why do we need it?
**A:** Proof Key for Code Exchange prevents authorization code interception attacks. Since mobile apps can't securely store a Client Secret, they dynamically generate a code verifier and challenge for each request.

## 13. Production Checklist
- [ ] `OAUTH_PKCE_ENABLED = True`
- [ ] `django-allauth` is configured.
- [ ] Validated that social accounts only link if emails are verified by the provider.
