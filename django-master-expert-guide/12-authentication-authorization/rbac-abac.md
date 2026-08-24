# RBAC & ABAC in Django

## 1. Mental Model
```text
[ RBAC - Role Based ]
User -> Belongs to Group ("Editors") -> Group has Permission ("app.change_article")
Check: user.has_perm("app.change_article")

[ ABAC - Attribute Based ]
User -> Has attribute (department="HR", level=5) -> Resource has attribute (doc_type="salary")
Check: user.department == "HR" and user.level >= doc.required_level
```

## 2. Why It Exists
To separate Authentication (Who are you?) from Authorization (What can you do?). Django provides a robust RBAC system via `Groups` and `Permissions`. ABAC is often implemented custom for finer-grained control.

## 3. Internal Working
When `has_perm()` is called, Django checks:
1. Is the user `is_superuser`? (Returns True)
2. Does the user have the permission directly in `user_permissions`?
3. Does the user belong to a group in `groups` that has the permission?
Django caches permissions on the user object in memory for the duration of the request to prevent N+1 queries.

## 4. Basic Implementation vs 5. Production-Ready Implementation

### Basic 🟡
Using `@permission_required('app.view_model')` on views.

### Production-Ready 🟢
Creating custom permissions in models and using custom backend or ABAC logic.
```python
# models.py
class Document(models.Model):
    title = models.CharField(max_length=200)
    department = models.CharField(max_length=50) # For ABAC
    
    class Meta:
        permissions = [
            ("publish_document", "Can publish document"),
            ("archive_document", "Can archive document"),
        ]

# ABAC implementation in a service layer or DRF permission class
from rest_framework import permissions

class IsDepartmentManager(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # ABAC: Only allow if user is in the same department and is a manager
        return request.user.department == obj.department and request.user.role == 'Manager'
```

## 6. Anti-Patterns
🔴 **Anti-Pattern:** Hardcoding role checks in views: `if user.group.name == 'Admin':`
*Why it's bad:* Group names can change. Always check *permissions*, not *groups*. `if user.has_perm('app.do_thing'):` is robust.

## 7. Environment-Specific Behavior
| Environment | Behavior |
|-------------|----------|
| Migrations | Django creates ContentTypes and Permissions during the `post_migrate` signal. |
| Tests | Permissions might not exist if running tests without migrations (`--nomigrations`). |

## 8. Local Development Issues
🔴 SYMPTOM: `user.has_perm()` returns False even though the model has `permissions` in `Meta`.
🔍 CAUSE: `makemigrations` and `migrate` haven't been run, so the `post_migrate` signal hasn't inserted the permissions into the DB.
🔧 FIX: Run `python manage.py makemigrations` and `python manage.py migrate`.

## 9. Production Issues
🔴 INCIDENT: **Massive DB Load from Permission Checks**
- **Severity:** Medium
- **Investigation:** An API endpoint checking permissions on 100 items caused 100 queries.
- **Root Cause:** Calling `has_object_permission` dynamically without prefetching user groups and permissions.
- **Fix:** If doing bulk operations, prefetch or load permissions once, or use a custom query `qs.filter(department=request.user.department)`.

## 10. Failure Simulation
Delete rows from `django_content_type`. Watch all permission checks fail and the admin panel break.

## 11. Decision Matrix
| Need | Solution |
|------|----------|
| Broad categories (Admin, Editor) | Django Groups & Permissions (RBAC) |
| Dynamic rules (Owner, Same Dept) | Custom Logic / ABAC |
| Row-level specific (User A can edit Post B) | Object-Level Permissions (django-guardian) |

## 12. Senior-Level Questions
**Q:** Does `user.has_perm()` hit the database every time?
**A:** Only the first time it is called per request. It populates `user._perm_cache`. However, if you load 50 users in a loop and call `has_perm` on each, it WILL hit the DB 50 times unless optimized.

## 13. Production Checklist
- [ ] Check permissions, not group names.
- [ ] Custom permissions defined in model `Meta`.
- [ ] ABAC rules are documented and unit tested extensively.
