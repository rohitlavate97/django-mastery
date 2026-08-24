# Session Management in Django

## 1. Mental Model
```text
[ Browser ] --(Cookie: sessionid=xyz123)--> [ Django Middleware ]
                                                  |
                                                  v
                                         [ Session Engine ]
                                          Looks up 'xyz123'
                                                  |
                                                  v
                                          { "_auth_user_id": "42" }
```

## 2. Why It Exists
HTTP is stateless. Sessions map subsequent requests from the same client to a persistent server-side dictionary.

## 3. Internal Working
`django.contrib.sessions.middleware.SessionMiddleware` extracts the session cookie. It uses the `SESSION_ENGINE` to load the session data and attaches it to `request.session`.

## 4. Basic Implementation vs 5. Production-Ready Implementation

### Basic (Default Django) 🟡
```python
# Uses the database, which is slow for high-traffic sites.
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
```

### Production-Ready [DJANGO 6.1+] 🟢
```python
# settings.py
# Use cached_db for persistence + speed
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'

# Security settings
SESSION_COOKIE_SECURE = True       # Only send over HTTPS
SESSION_COOKIE_HTTPONLY = True     # Prevent JS access (XSS mitigation)
SESSION_COOKIE_SAMESITE = 'Lax'    # CSRF protection ('Strict' if possible)
SESSION_COOKIE_AGE = 1209600       # 2 weeks
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
```

## 6. Anti-Patterns
🔴 **Anti-Pattern:** Storing large data (like search results) in `request.session`.
*Why it's bad:* Sessions are loaded into memory on *every* request. Large sessions bloat memory and slow down the cache/DB.

## 7. Environment-Specific Behavior
| Environment | Behavior |
|-------------|----------|
| Local | `SESSION_COOKIE_SECURE = False` usually needed if not using HTTPS locally. |
| Production | Must have `SESSION_COOKIE_SECURE = True`. |

## 8. Local Development Issues
🔴 SYMPTOM: Unable to log in locally.
🔍 CAUSE: `SESSION_COOKIE_SECURE = True` but accessing via `http://localhost`.
🔧 FIX: 
```python
# In local settings
SESSION_COOKIE_SECURE = False
```

## 9. Production Issues
🔴 INCIDENT: **Mass User Logout on Password Change**
- **Severity:** Medium
- **Investigation:** Users reported being logged out after changing their passwords.
- **Root Cause:** Changing a password changes the user's `session_auth_hash`. Existing sessions invalidate.
- **Fix:** Use `update_session_auth_hash(request, user)` in the password change view to update the session without dropping it.

## 10. Failure Simulation
Change a user's password directly in the DB. Try to use an existing session cookie for that user. Django will reject it.

## 11. Decision Matrix
| Engine | Speed | Persistence | Best For |
|--------|-------|-------------|----------|
| `db` | Slow | High | Small sites |
| `cache` | Very Fast | Low (eviction) | Temporary data |
| `cached_db` | Fast | High | **Production Standard** |
| `signed_cookies`| Fast | None (Client) | Stateless, but limited to 4KB and poses security risks if SECRET_KEY leaks. |

## 12. Senior-Level Questions
**Q:** How do you prevent Session Fixation in Django?
**A:** Django naturally prevents this. On login, `django.contrib.auth.login()` calls `request.session.cycle_key()`, which creates a brand new session ID while preserving the data.

## 13. Production Checklist
- [ ] `SESSION_ENGINE` set to `cached_db` or Redis cache.
- [ ] `SESSION_COOKIE_SECURE = True`
- [ ] `SESSION_COOKIE_HTTPONLY = True`
- [ ] Periodically run `python manage.py clearsessions` via cron.
