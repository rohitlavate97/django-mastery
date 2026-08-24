# Feature Flags in Django

## 1. Mental Model
```text
User Request --> View
                  |
                  v
          [Feature Flag Check]
             /            \
       (Enabled)        (Disabled)
          /                  \
[Execute New Logic]    [Execute Old Logic]
```

## 2. Why It Exists
Deployments should not equal releases. Feature flags decouple the deployment of code from the exposure of that code to users. This allows for trunk-based development (merging to main frequently), gradual rollouts (canary releases), A/B testing, and emergency kill switches if a new feature causes site instability.

## 3. Internal Working
Flags are typically stored in the database or a high-speed cache like Redis. When a code path is hit, Django queries the flag store to determine if the flag is active for the current context (e.g., the specific user, or a percentage of users).

## 4. Basic Implementation
Using `django-waffle` for basic database-backed flags.

```python
# views.py
from waffle.decorators import waffle_flag
from django.shortcuts import render

@waffle_flag('new_checkout_flow')
def checkout(request):
    # This view is only accessible if the flag is active
    return render(request, 'new_checkout.html')

# For inline logic
import waffle

def calculate_tax(request, amount):
    if waffle.flag_is_active(request, 'new_tax_engine'):
        return NewTaxEngine.calculate(amount)
    return OldTaxEngine.calculate(amount)
```

## 5. Production-Ready Implementation
Database-backed flags add a DB query to every check. In production, flags must be cached to avoid destroying DB performance. Also, tying flags to User models allows targeting specific cohorts.

```python
# settings.py
# Using django-waffle with Redis caching
WAFFLE_CACHE_PREFIX = 'waffle:'
WAFFLE_CACHE_NAME = 'default' # Ensure this points to Redis
WAFFLE_FLAG_DEFAULT = False

# views.py
from waffle import flag_is_active
import logging

logger = logging.getLogger(__name__)

def process_payment(request, order):
    # 1. Check flag (hits Redis, not DB)
    if flag_is_active(request, 'stripe_integration_v2'):
        try:
            return StripeV2.charge(order)
        except Exception as e:
            logger.error("Stripe V2 failed, falling back", exc_info=True)
            # 2. Fallback logic on failure
            pass
            
    # Legacy flow
    return LegacyPayment.charge(order)
```

## 6. Anti-Patterns
🔴 **Ticking Time Bomb:**
```python
# views.py
if settings.NEW_FEATURE_ENABLED:
    run_new_feature()
```
*Why it's bad:* Hardcoding feature flags in `settings.py` requires a full application redeploy/restart to toggle the feature. This defeats the purpose of a fast emergency kill switch.

## 7. Environment-Specific Behavior
| Feature | Local | Staging | Production |
|---------|-------|---------|------------|
| Flag State | Manual via Admin | Mostly ON for QA | Gradual rollout (10% -> 50% -> 100%) |
| Storage | SQLite | DB + Redis | Managed Service (LaunchDarkly) or DB+Redis |

## 8. Local Development Issues
🔴 SYMPTOM: Flag is active in admin, but `flag_is_active()` returns False.
🔍 CAUSE: Local cache is stale, or the flag is configured for "Authenticated Users Only" and you are testing anonymously.
🔧 FIX: Clear your local cache (`cache.clear()`) and verify the specific conditions of the flag in the Django admin.

## 9. Production Issues
🔴 INCIDENT: DB Connection Pool Exhaustion
- **Severity:** CRITICAL
- **Investigation:** A highly-trafficked middleware was checking a database-backed feature flag on every single request.
- **Root Cause:** Caching was not configured for the feature flag library, resulting in a 1:1 ratio of web requests to flag DB queries.
- **Fix:** Enabled Redis caching for feature flags with a 60-second TTL.

## 10. Failure Simulation
Turn off your Redis server locally. If your feature flags rely on it, the app might crash. A robust implementation should gracefully fallback to `False` (or the default state) if the flag store is unreachable, rather than returning a 500.

## 11. Decision Matrix
| Tool | Pros | Cons |
|------|------|------|
| `django-waffle` | Free, DB-backed, native | Managing cache invalidation is manual |
| LaunchDarkly | Enterprise grade, fast, UI | Expensive, adds network latency |
| Custom DB Model | Complete control | You have to build the caching layer yourself |

## 12. Senior-Level Questions
**Q: How do you clean up feature flags, and why is it important?**
A: Flags create "technical debt by design" (multiple code paths). Once a feature is 100% rolled out and stable, you must schedule a PR to remove the flag, delete the old code path, and drop the flag from the DB. Leftover flags clutter the codebase and make testing harder.

## 13. Production Checklist
- [ ] Feature flag checks are cached to prevent DB load.
- [ ] The default state (if the flag store fails) is defined and safe.
- [ ] A calendar reminder or Jira ticket exists to remove the flag after full rollout.
