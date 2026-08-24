# Deployment Checklist & System Checks

## 1. Mental Model
```text
[Developer]
     |
     v
[python manage.py check --deploy]
     |
     v
[Django System Check Framework]
  |-- Security Checks (HTTPS, CSRF, XSS)
  |-- Database Checks
  |-- Cache Checks
     |
     v
[CI/CD Pipeline] -> Fails if warnings exist -> [Production]
```

## 2. Why It Exists
Deploying a Django application involves dozens of configuration settings (`SECURE_*`, `CSRF_*`, `SESSION_*`). Missing even one can result in severe security vulnerabilities (e.g., sessions being transmitted over unencrypted HTTP). The system check framework automates the verification of these settings.

## 3. Internal Working
When `check --deploy` is executed, Django iterates through a registry of check functions. The `--deploy` flag specifically triggers checks tagged with `Tags.security` and `Tags.compatibility`, which evaluate settings against production best practices.

## 4. Basic Implementation
Running the built-in deployment checks:

```bash
# In your terminal, using the production settings module
export DJANGO_SETTINGS_MODULE=project.settings.production
python manage.py check --deploy
```

*Output Example:*
```text
System check identified some issues:

WARNINGS:
?: (security.W004) You have not set a value for the SECURE_HSTS_SECONDS setting...
?: (security.W008) Your SECURE_SSL_REDIRECT setting is not set to True...
```

## 5. Production-Ready Implementation
You should write custom system checks to enforce your organization's specific architectural rules, such as ensuring `ADMIN_URL` is never default, or that specific middlewaress are loaded.

```python
# app/apps.py or a dedicated checks.py
from django.core.checks import register, Warning, Error, Tags
from django.conf import settings

@register(Tags.security)
def check_admin_url_is_obfuscated(app_configs, **kwargs):
    errors = []
    
    # Example custom rule: Don't use the default 'admin/' path
    if hasattr(settings, 'ADMIN_URL') and settings.ADMIN_URL == 'admin/':
        errors.append(
            Warning(
                "The ADMIN_URL is set to the default 'admin/'.",
                hint="Change ADMIN_URL in production settings to an obfuscated string.",
                id="myproject.W001",
            )
        )
    return errors
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:**
```bash
# In CI/CD pipeline
python manage.py test
docker build -t myapp .
```
*Why it's bad:* Failing to run `check --deploy` in CI means a developer could accidentally merge code that turns off `SESSION_COOKIE_SECURE` or leaves `DEBUG = True`, and the pipeline would pass it straight to production.

## 7. Environment-Specific Behavior
| Environment | Command | Expected Result |
|-------------|---------|-----------------|
| Local       | `check` | Passes (ignoring deploy warnings) |
| CI/CD       | `check --deploy` | MUST Pass (Fail build on warnings) |
| Production  | `check --deploy` | Clean output |

## 8. Local Development Issues
🔴 SYMPTOM: `manage.py check --deploy` throws `security.W008 (SECURE_SSL_REDIRECT)`.
🔍 CAUSE: You ran the deploy check using your local development settings, which shouldn't enforce SSL redirects.
🔧 FIX: Always run `--deploy` using the production settings module.

## 9. Production Issues
🔴 INCIDENT: `DEBUG = True` Leaked in Production
- **Severity:** CRITICAL
- **Investigation:** A 500 error revealed source code and environment variables to users.
- **Root Cause:** A misconfigured `.env` file caused the app to fall back to `DEBUG=True`.
- **Fix:** Added `python manage.py check --deploy` to the Kubernetes pre-deploy hook. Django's deploy check will immediately throw an Error (not a Warning) if `DEBUG = True`.

## 10. Failure Simulation
Set `DEBUG = True` in your production settings and run `python manage.py check --deploy --fail-level WARNING`. Observe how the command exits with a non-zero status code (which would fail a CI pipeline).

## 11. Decision Matrix
| Check Tool | Scope | When to Use |
|------------|-------|-------------|
| `manage.py check` | Django configuration | CI/CD pipelines |
| Bandit | Python source code (AST) | SAST security scanning |
| Safety | Python dependencies | Checking for CVEs in requirements |

## 12. Senior-Level Questions
**Q: If you are behind a reverse proxy (like Nginx or AWS ALB) that handles SSL termination, setting `SECURE_SSL_REDIRECT = True` can cause infinite redirect loops. How do you solve this?**
A: You must tell Django to trust the proxy's headers. Set `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` so Django knows the original request was secure, satisfying the deployment check and preventing the loop.

## 13. Production Checklist
- [ ] `python manage.py check --deploy` runs in the CI pipeline and blocks deployment on failure.
- [ ] `SECURE_BROWSER_XSS_FILTER = True`
- [ ] `SECURE_CONTENT_TYPE_NOSNIFF = True`
- [ ] `SESSION_COOKIE_SECURE = True`
- [ ] `CSRF_COOKIE_SECURE = True`
- [ ] Custom checks exist for organization-specific architecture rules.
