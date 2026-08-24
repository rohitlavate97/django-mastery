# Web Security Fundamentals for Django

## 1. Mental Model: The Security Perimeters

```text
+-----------------------+           +-----------------------+
|  Client Browser       |           |   Django Server       |
|                       |  Network  |                       |
| 1. Same-Origin Policy | <=======> | 6. Host Header Val    |
| 2. CSRF Tokens        | (HTTPS)   | 7. CSRF Middleware    |
| 3. XSS Escaping       |           | 8. Auth/Permissions   |
| 4. CSP Enforcement    |           | 9. ORM (SQLi defense) |
| 5. Secure Cookies     |           | 10. CORS Middleware   |
+-----------------------+           +-----------------------+
```

Web security in Django operates on a shared responsibility model between the client (Browser) and the server (Django). Django provides robust defense-in-depth mechanisms, but they must be explicitly configured and understood to be effective.

## 2. Same-Origin Policy (SOP) & CORS

**SOP**: A browser security mechanism that prevents a script loaded from `origin A` from reading data on `origin B`. 
*Origin* = Scheme + Host + Port (e.g., `https://example.com:443`).

**CORS (Cross-Origin Resource Sharing)**: A mechanism to bypass SOP safely. If your frontend is on `app.example.com` and Django API is on `api.example.com`, they are cross-origin.

### Django CORS Implementation
Use `django-cors-headers`.

```python
# settings.py
INSTALLED_APPS += ['corsheaders']
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware', # MUST be top of the list!
    'django.middleware.common.CommonMiddleware',
    ...
]

# 💣 Anti-Pattern: CORS_ALLOW_ALL_ORIGINS = True (Vulnerable to data theft)
CORS_ALLOWED_ORIGINS = [
    "https://app.example.com",
]
CORS_ALLOW_CREDENTIALS = True # Allows cookies to be included in cross-origin requests
```

## 3. Cross-Site Request Forgery (CSRF)

**How it works**: A user logs into your bank. Attacker tricks user into visiting `evil.com`. `evil.com` sends a hidden POST request to `bank.com/transfer`. Because the browser automatically attaches the user's session cookie for `bank.com`, the transfer succeeds.

**Django's Defense**: Double-Submit Cookie Pattern + Referer Checking.
1. Django sends a `csrftoken` cookie.
2. Forms include a hidden `<input name="csrfmiddlewaretoken">` (or frontend sends `X-CSRFToken` header).
3. `CsrfViewMiddleware` verifies that the cookie matches the submitted token, AND (if HTTPS) that the `Referer` header matches the origin.

### 🔧 Configuration
```python
CSRF_COOKIE_SECURE = True     # Only send over HTTPS
CSRF_COOKIE_HTTPONLY = False  # Must be False if JS frontend needs to read it
CSRF_TRUSTED_ORIGINS = ['https://app.example.com'] # Crucial for cross-origin setups
```

## 4. Cross-Site Scripting (XSS)

**How it works**: Attacker injects malicious JavaScript into your site, which executes in a victim's browser, stealing their session.

**Django's Defense**: 
- **Auto-escaping**: Django templates automatically escape HTML characters (`<` becomes `&lt;`).
- **CSP**: Content Security Policy restricts where scripts can load from.

### 💣 Anti-Pattern: Bypassing Auto-escape
```html
<!-- DANGEROUS: If user.bio contains <script>, it executes! -->
<div>{{ user.bio|safe }}</div> 
```

### Production CSP Implementation
Use `django-csp`.
```python
# settings.py
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "https://trusted-cdn.com", "'nonce-{request.csp_nonce}'")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'") # Inline styles often needed
```

## 5. Cookie Security Attributes

Django configures cookies via settings. Secure cookies prevent theft via MITM or XSS.

| Attribute | Meaning | Django Setting |
| :--- | :--- | :--- |
| **Secure** | Only transmit over HTTPS. | `SESSION_COOKIE_SECURE = True` |
| **HttpOnly** | JS cannot access via `document.cookie`. (Mitigates XSS). | `SESSION_COOKIE_HTTPONLY = True` |
| **SameSite** | Controls if cookie is sent in cross-site requests. | `SESSION_COOKIE_SAMESITE = 'Lax'` |
| **Domain** | Scopes cookie to specific subdomains. | `SESSION_COOKIE_DOMAIN = None` |

## 6. Clickjacking

**How it works**: Attacker loads your site in a transparent `<iframe>` overlaid on a harmless-looking button. User clicks the button, but actually clicks a critical action on your site.

**Django's Defense**: `XFrameOptionsMiddleware`.
```python
X_FRAME_OPTIONS = 'DENY' # Or 'SAMEORIGIN'
```

## 7. Server-Side Request Forgery (SSRF)

**How it works**: Attacker forces your Django backend to make HTTP requests to internal, protected resources (e.g., AWS Metadata IP `169.254.169.254`).

### 💣 Anti-Pattern: Unvalidated webhooks
```python
import requests
def fetch_avatar(request):
    url = request.GET.get('url')
    # DANGEROUS: Attacker sends url="http://169.254.169.254/latest/meta-data/iam/security-credentials/"
    res = requests.get(url) 
    return HttpResponse(res.content)
```

**Fix**: Strictly validate URLs, enforce protocol (`https://`), restrict hostnames, and ideally route outbound proxy traffic through a restricted egress proxy.

## 8. HTTPS Enforcement & HSTS

Ensure clients never communicate over plaintext HTTP.

```python
# settings.py
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

## 9. Production Issues

### 🔴 INCIDENT: Mass Account Takeover via XSS
**Severity**: CRITICAL
**Investigation**: Attackers injected an SVG image into the user profile avatar field. When admins viewed the profile, the SVG executed JS (SVGs can contain `<script>` tags!). The JS read the admin's session cookie and sent it to `evil.com`.
**Root Cause**: User uploads were served from the same domain as the main app (`app.com/media/`), and session cookies lacked `HttpOnly` or the frontend didn't enforce a CSP.
**Fix**: 
1. Serve user-uploaded media from a distinct domain (e.g., `user-content.com`).
2. Enforce Strict CSP.
3. Ensure `SESSION_COOKIE_HTTPONLY = True`.

## 10. Checklist for Production
- [ ] Run `python manage.py check --deploy`.
- [ ] Set `DEBUG = False`.
- [ ] Verify `ALLOWED_HOSTS` is strictly defined.
- [ ] Enable all `SECURE_*` settings (HSTS, SSL Redirect).
- [ ] Configure `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE`.
- [ ] Use `django-environ` to keep secrets out of source code.
- [ ] Implement rate limiting (e.g., `django-ratelimit`) on login endpoints to prevent brute force.
