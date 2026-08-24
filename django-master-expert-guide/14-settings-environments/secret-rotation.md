# Zero-Downtime Secret Rotation

## 1. Mental Model
```text
[Current State]
App -> Uses Old Key

[Phase 1: Distribute]
App -> Accepts Old Key + New Key
(Traffic still signed with Old Key, but can read New Key)

[Phase 2: Transition]
App -> Signs with New Key, Accepts Old Key + New Key
(New data uses New Key, old data still valid)

[Phase 3: Cleanup]
App -> Uses New Key Only
(Old Key revoked)
```

## 2. Why It Exists
Secrets (`SECRET_KEY`, Database Passwords, API Keys) leak. If you only support a single secret at a time, changing it will instantly invalidate all active user sessions, password reset tokens, and encrypted database fields, causing massive downtime and user disruption.

## 3. Internal Working
Django 4.1+ introduced the `SECRET_KEY_FALLBACKS` setting. When Django verifies a cryptographic signature (like a session cookie), it first tries `SECRET_KEY`. If it fails, it tries the keys in `SECRET_KEY_FALLBACKS`. For signing new data, it only ever uses `SECRET_KEY`.

## 4. Basic Implementation
Rotating Django's core `SECRET_KEY`.

`settings/production.py`:
```python
import environ
env = environ.Env()

# The new key you are transitioning to
SECRET_KEY = env('DJANGO_SECRET_KEY')

# The old keys you are transitioning away from
SECRET_KEY_FALLBACKS = env.list('DJANGO_SECRET_KEY_FALLBACKS', default=[])
```

`.env` configuration during Transition:
```env
DJANGO_SECRET_KEY="new-secure-key"
DJANGO_SECRET_KEY_FALLBACKS="old-compromised-key"
```

## 5. Production-Ready Implementation
Rotating a Database Password without downtime requires infrastructure orchestration, not just Django code.

1. **DB Side:** Create a second database user (`app_user_v2`) with identical permissions to the current user (`app_user_v1`).
2. **Django Side (Env):** Update the `DATABASE_URL` in the environment to use `app_user_v2` and restart the application nodes gradually (rolling restart).
3. **Verify:** Check logs and APM to ensure all nodes are using the new user.
4. **DB Side:** Drop `app_user_v1`.

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:**
```python
# settings.py
SECRET_KEY = "my-hardcoded-secret-key"
```
*Why it's bad:* Hardcoded keys mean you have to deploy code to rotate a key. Furthermore, the key is permanently in Git history. If leaked, you have no fallback mechanism.

## 7. Environment-Specific Behavior
| Feature | Local | Staging | Production |
|---------|-------|---------|------------|
| Fallbacks | Rarely needed | Good for testing process | Absolutely mandatory |
| Secret Manager | `.env` | AWS Secrets Manager / Hashicorp Vault | AWS Secrets Manager / Hashicorp Vault |

## 8. Local Development Issues
🔴 SYMPTOM: `django.core.exceptions.ImproperlyConfigured: The SECRET_KEY setting must not be empty.`
🔍 CAUSE: When setting up rotation, the primary `SECRET_KEY` was left blank in the `.env` file.
🔧 FIX: Ensure the new key is defined as `SECRET_KEY` and the old one is moved to the fallback list.

## 9. Production Issues
🔴 INCIDENT: Mass Session Invalidation
- **Severity:** HIGH
- **Investigation:** Millions of users were logged out simultaneously after a deployment.
- **Root Cause:** A developer rotated the `SECRET_KEY` without adding the old key to `SECRET_KEY_FALLBACKS`. All existing session cookies became cryptographically invalid.
- **Fix:** Restored the old key into `SECRET_KEY_FALLBACKS` and triggered a rolling restart.

## 10. Failure Simulation
Change your local `SECRET_KEY` without using fallbacks. Observe that your admin session is instantly destroyed and you must log in again. Then, set it back, use fallbacks, and observe the session remains valid.

## 11. Decision Matrix
| Rotation Type | Approach | Complexity |
|---------------|----------|------------|
| Django Sessions/Tokens | `SECRET_KEY_FALLBACKS` | Low |
| Database Passwords | Multi-user overlap | Medium |
| Encrypted DB Fields | Background migration task | High |

## 12. Senior-Level Questions
**Q: How do you rotate a secret used to encrypt data at rest (e.g., credit card tokens in the DB)?**
A: This requires a multi-step migration. 1. Introduce a new key and update the model to try decrypting with New, then Old. 2. Write a background worker that reads every row with the Old key, encrypts with the New key, and saves. 3. Once all rows are migrated, remove the Old key.

## 13. Production Checklist
- [ ] `SECRET_KEY_FALLBACKS` is configured in production settings.
- [ ] Secrets are injected via environment variables or a Secret Manager, not hardcoded.
- [ ] Database credentials can be rotated via infrastructure without deploying code.
