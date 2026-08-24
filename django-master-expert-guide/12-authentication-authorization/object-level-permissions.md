# Object-Level Permissions in Django

## 1. Mental Model
```text
[ Global Permission ] 
User can "change_article" -> Can edit ALL articles.

[ Object-Level Permission ]
User can "change_article" ON Article ID #42 ONLY.
```

## 2. Why It Exists
Standard Django permissions are table-wide. In multi-tenant apps, SAAS, or social networks, users own specific rows and should only have access to those rows.

## 3. Internal Working
Django's auth backend supports passing an object: `user.has_perm('app.change_article', obj=article)`. However, the default `ModelBackend` simply ignores the `obj` and falls back to global permissions. To make it work, you need a custom backend or a library like `django-guardian`.

## 4. Basic Implementation vs 5. Production-Ready Implementation

### Basic (Custom Lightweight) 🟡
```python
# Just checking a ForeignKey
def can_edit(user, article):
    return article.author_id == user.id
```
*Pros:* Fast, no extra tables. *Cons:* Doesn't scale to complex sharing rules (e.g., sharing with 5 specific users).

### Production-Ready (django-guardian) 🟢
```python
# settings.py
INSTALLED_APPS += ['guardian']
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
)

# Usage
from guardian.shortcuts import assign_perm, get_objects_for_user

# Assign permission
assign_perm('change_article', user, article)

# Check permission
user.has_perm('change_article', article) # Returns True

# FAST Querying (Avoids N+1)
# Gets all articles the user has 'change_article' permission for
editable_articles = get_objects_for_user(user, 'app.change_article')
```

## 6. Anti-Patterns
🔴 **Anti-Pattern:** Filtering querysets in Python instead of the DB.
```python
# BAD
articles = [a for a in Article.objects.all() if user.has_perm('view', a)]
```
*Why it's bad:* Pulls the entire table into memory and does thousands of queries. Use `get_objects_for_user` to do the filtering via SQL `JOIN`s.

## 7. Environment-Specific Behavior
| Environment | Behavior |
|-------------|----------|
| DB Engine | `django-guardian` creates generic foreign keys. Performance depends heavily on DB indexing (Postgres handles this well). |

## 8. Local Development Issues
🔴 SYMPTOM: `AnonymousUser` object raises errors when checking object permissions.
🔍 CAUSE: `django-guardian` relies on the database, and `AnonymousUser` isn't in the DB.
🔧 FIX: Guardian handles `AnonymousUser` gracefully if configured, or use `if not request.user.is_authenticated: return False`.

## 9. Production Issues
🔴 INCIDENT: **Query Timeout on Dashboard**
- **Severity:** High
- **Investigation:** The dashboard loaded all items a user had access to. The query took 15 seconds.
- **Root Cause:** `django-guardian` uses `GenericForeignKey` under the hood. The `guardian_userobjectpermission` table grew to millions of rows, and the joins became incredibly slow.
- **Fix:** Dropped `django-guardian` for that specific high-volume model. Refactored the schema to use a direct ManyToMany field (`collaborators = models.ManyToManyField(User)`) which is significantly faster for simple sharing.

## 10. Failure Simulation
Assign permissions to an object, then delete the object. Because Guardian uses Generic Foreign Keys, sometimes orphaned permission rows remain depending on configuration.

## 11. Decision Matrix
| Scenario | Solution |
|----------|----------|
| User owns the row exclusively | Direct ForeignKey (`author=user`) |
| Shared with a few users/groups | ManyToManyField (`viewers=users`) |
| Complex mixed permissions | `django-guardian` |

## 12. Senior-Level Questions
**Q:** Why is `django-guardian` considered heavy?
**A:** It creates rows in a central permissions table linking User ID, Permission ID, ContentType ID, and Object ID. This table grows factorially ($Users \times Objects \times Permissions$). For large datasets, direct DB relations are faster.

## 13. Production Checklist
- [ ] `guardian.backends.ObjectPermissionBackend` added to `AUTHENTICATION_BACKENDS`.
- [ ] Used `get_objects_for_user` instead of loop-based permission checks.
- [ ] Evaluated if direct ForeignKeys would suffice before adopting Guardian.
