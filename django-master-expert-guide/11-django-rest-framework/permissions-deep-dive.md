# Permissions Deep Dive in DRF

## 1. Mental Model

```text
Request Pipeline
      |
      v
Authentication (Who is this?) -> success
      |
      v
Global / View Level Permissions `has_permission()`
      |-- (Is user authenticated? Does user have role X?)
      v
View execution (get_object() called)
      |
      v
Object Level Permissions `has_object_permission()`
      |-- (Is this user the owner of THIS specific object?)
      v
Response
```

## 2. Why It Exists
Decoupling access control logic from business logic ensures that security checks are strictly enforced and easily auditable.

## 3. Global vs View-Level vs Object-Level

- **Global**: `REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES']` - applied to ALL views.
- **View-Level**: `permission_classes = [...]` - applied to specific view. Checks `has_permission()`.
- **Object-Level**: Triggered ONLY when `.get_object()` is called. Checks `has_object_permission()`.

### 🔴 The List View Security Hole
`has_object_permission()` is **NEVER** called on list views (`ListAPIView`, `ModelViewSet.list`).
If you rely on object permissions to hide items, list views will leak data!
**Fix**: Always override `get_queryset()` to filter items the user is allowed to see.

## 4. Production-Ready Custom Permissions

```python
from rest_framework import permissions

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object or admins to edit it.
    Assumes the model instance has an `owner` attribute.
    """
    message = "You must be the owner of this object to access it."

    def has_permission(self, request, view):
        # Must be authenticated to even try
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner or admin.
        return obj.owner == request.user or request.user.is_staff
```

## 5. Bitwise Combination of Permissions
DRF allows composing permissions using `|` (OR), `&` (AND), and `~` (NOT).

```python
class MyViewSet(viewsets.ModelViewSet):
    # User must be authenticated AND (be an admin OR be in the beta group)
    permission_classes = [IsAuthenticated & (IsAdminUser | IsBetaUser)]
```

## 6. Environment Specifics
- **Testing**: Use `APIClient.force_authenticate(user)` to bypass auth backends but strictly test permission classes.

## 7. Production Checklist
- [ ] `has_object_permission` is backed by `get_queryset` filtering for list views.
- [ ] Permission logic does not result in N+1 database queries.
- [ ] Used bitwise operators for complex permission logic instead of writing monolithic permission classes.
