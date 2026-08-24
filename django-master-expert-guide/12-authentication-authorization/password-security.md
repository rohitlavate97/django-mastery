# Password Security in Django

## 1. Mental Model
```text
[ User types password ] --> "my_super_secret"
       |
       v
[ Django hasher (e.g., Argon2) ] --> uses salt + cost factors + algorithm
       |
       v
[ Database Storage ] --> "argon2$argon2id$v=19$m=102400,t=2,p=8$salt$hash"
```

## 2. Why It Exists
Storing plaintext passwords is the cardinal sin of security. Hashes must be computationally expensive to resist brute-force and dictionary attacks (GPU cracking).

## 3. Internal Working
Django uses a list of `PASSWORD_HASHERS`. When checking a password, it reads the prefix of the DB hash (e.g., `pbkdf2_sha256$`) to determine which hasher to use. 

## 4. Basic Implementation vs 5. Production-Ready Implementation

### Basic (Default Django) 🟡
```python
# settings.py defaults to PBKDF2
# It is "okay", but Argon2 is the winner of the Password Hashing Competition.
```

### Production-Ready [DJANGO 6.1+] 🟢
```python
# settings.py
# Install argon2-cffi
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher', # Preferred
    'django.contrib.auth.hashers.PBKDF2PasswordHasher', # Fallback for old hashes
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 12}, # OWASP recommends at least 12
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]
```

## 6. Anti-Patterns
🔴 **Anti-Pattern:** Removing old hashers from `PASSWORD_HASHERS`.
*Why it's bad:* Users with old hashes will be permanently locked out because Django won't know how to verify their old hash. Django automatically upgrades hashes on successful login if a better hasher is placed higher in the list!

## 7. Environment-Specific Behavior
| Environment | Behavior |
|-------------|----------|
| Local/Testing | Argon2 makes tests extremely slow due to computational cost. |
| Production | Provides necessary security against GPU cracking. |

## 8. Local Development Issues
🔴 SYMPTOM: Test suite takes 10+ minutes to run.
🔍 CAUSE: Argon2 or PBKDF2 hashing happens on every user creation in tests.
🔧 FIX: Override `PASSWORD_HASHERS` in test settings to use MD5:
```python
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
```

## 9. Production Issues
🔴 INCIDENT: **Server CPU Spikes to 100%**
- **Severity:** High
- **Investigation:** A botnet is attempting credential stuffing, hitting the login endpoint 500 times per second.
- **Root Cause:** Argon2 is designed to use CPU and Memory. Massive concurrent logins cause Resource Exhaustion (DoS).
- **Fix:** Implement rate limiting (e.g., `django-ratelimit` or WAF) on the login endpoint.

## 10. Failure Simulation
Attempt to login with a user whose password was hashed with a removed hasher. Django will throw `ValueError: Unknown password hashing algorithm`.

## 11. Decision Matrix
| Algorithm | CPU Cost | Memory Cost | Django Support | Verdict |
|-----------|----------|-------------|----------------|---------|
| Argon2 | High | High | Yes (via `argon2-cffi`) | **Best** |
| BCrypt | High | Low | Yes (via `bcrypt`) | Good |
| PBKDF2 | High | Low | Yes (Built-in) | Default/Acceptable |

## 12. Senior-Level Questions
**Q:** How does Django upgrade passwords transparently?
**A:** When `check_password()` succeeds, Django checks if the hasher used is the first one in `PASSWORD_HASHERS`. If not, it re-hashes the plaintext password with the top hasher and saves it.

## 13. Production Checklist
- [ ] Argon2 is first in `PASSWORD_HASHERS`.
- [ ] Minimum password length is 12.
- [ ] Rate limiting is applied to the login endpoint.
- [ ] Test settings use MD5 hasher.
