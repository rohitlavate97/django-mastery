# Django Mastery: Security Audit Checklist

A 50-point comprehensive security verification for enterprise Django applications.

## 1. Authentication & Authorization (OWASP A01 & A07)

- [ ] Ensure all API endpoints require authentication by default (e.g., DRF `IsAuthenticated` global policy).
- [ ] Verify `User.set_password()` is used everywhere; never assign plain text to `User.password`.
- [ ] Use Argon2 or bcrypt password hashers (`PASSWORD_HASHERS`).
- [ ] Implement account lockout after N failed login attempts (e.g., `django-axes`).
- [ ] Ensure Object-Level permissions (e.g., `django-guardian` or custom QuerySet filtering) prevent IDOR.
- [ ] Validate multi-tenant data boundaries (e.g., filter all querysets by `request.user.tenant`).
- [ ] Enforce MFA (Multi-Factor Authentication) for admin access.

## 2. CSRF & CORS (OWASP A05)

- [ ] Ensure `CsrfViewMiddleware` is active in `MIDDLEWARE`.
- [ ] Verify `@csrf_exempt` is ONLY used on webhook endpoints and strictly validated via HMAC signatures.
- [ ] Check `CORS_ALLOWED_ORIGINS` (via `django-cors-headers`). NEVER use `CORS_ALLOW_ALL_ORIGINS = True` in production.
- [ ] Ensure `CORS_ALLOW_CREDENTIALS` is carefully managed and restricted.

## 3. Injection Prevention (OWASP A03)

- [ ] Never use `.extra()` on QuerySets. Rewrite to use `.annotate()` and `RawSQL` with parameterized queries.
- [ ] Never concatenate strings into `.raw()` queries. Always use the `params` argument.
- [ ] Validate all raw SQL functions against SQL injection.
- [ ] Prevent Command Injection: Avoid `os.system` or `subprocess.run` with user input. Use `shlex.quote` if absolutely necessary.
- [ ] Prevent Template Injection: Avoid marking strings as `safe` (`|safe`, `mark_safe()`) unless HTML is sanitized via `bleach` or `nh3`.

## 4. Data Exposure & Secrets (OWASP A02)

- [ ] Audit Git history with `trufflehog` or `gitleaks` to ensure no checked-in secrets.
- [ ] Ensure debug toolbars (e.g., `django-debug-toolbar`) are disabled in production.
- [ ] Filter sensitive variables in error reports (`@sensitive_variables()`, `@sensitive_post_parameters()`).
- [ ] Exclude fields like `password`, `is_superuser`, `is_staff` from all API serializers.

## 5. File Uploads & SSRF (OWASP A10 & A04)

- [ ] Limit file upload sizes via web server (Nginx `client_max_body_size`) and Django app logic.
- [ ] Validate uploaded file extensions and MIME types strictly.
- [ ] Scan uploaded files for malware if accessible by other users.
- [ ] Prevent Server-Side Request Forgery (SSRF) when the app fetches URLs (use restricted networks/proxies, avoid user-controlled URLs).

## 6. Infrastructure & HTTP

- [ ] Remove `Server` and `X-Powered-By` headers (hide OS and Python/Django versions).
- [ ] Verify rate limiting on critical endpoints (login, password reset, API routes) via DRF Throttling or API Gateway.
- [ ] Setup Content Security Policy (CSP) using `django-csp`.
- [ ] Run regular dependency vulnerability scans (`pip-audit` or Dependabot).
