# FBV vs CBV: Architecture, Trade-offs & Internals

## 1. Mental Model: Declarative vs Imperative

In Django, views are callables that take a web request and return a web response.
- **Function-Based Views (FBV)**: Imperative. Explicit control flow. You write the exact sequence of execution.
- **Class-Based Views (CBV)**: Declarative. Implicit control flow. You define properties and override specific methods within a pre-defined execution lifecycle.

```text
FBV Execution:
Request -> Function -> if GET -> Process -> Return Response
                    -> if POST -> Validate -> Process -> Return Response

CBV Execution:
Request -> as_view() -> View.__init__() -> dispatch() 
                                                |
                                                +-> get() -> Response
                                                +-> post() -> Response
```

### Why It Exists
CBVs were introduced to DRY (Don't Repeat Yourself) up view code, allowing inheritance and mixins. FBVs remain standard for complex, non-standard flows where overriding dozens of CBV methods becomes unreadable.

---

## 2. CBV Internals: Thread-Safety & `View.as_view()`

CBVs are classes, but Django's URL resolver expects a function. `View.as_view()` is the bridge.

### Internal Trace of `as_view()`
```python
# Conceptual trace of django/views/generic/base.py
class View:
    @classonlymethod
    def as_view(cls, **initkwargs):
        # 1. Validate initkwargs against class attributes
        for key in initkwargs:
            if not hasattr(cls, key):
                raise TypeError(...)

        # 2. Create the actual view function
        def view(request, *args, **kwargs):
            # 3. Instantiate the class per request (THREAD SAFETY!)
            self = cls(**initkwargs)
            self.setup(request, *args, **kwargs)
            if not hasattr(self, 'request'):
                raise AttributeError(...)
            # 4. Delegate to dispatch
            return self.dispatch(request, *args, **kwargs)

        # 5. Copy attributes and return closure
        update_wrapper(view, cls, updated=())
        return view
```
**Crucial Concept**: The class is instantiated *per request* inside the `view` closure. This ensures thread-safety. If the class was instantiated once and shared across requests, instance variables (`self.foo = 'bar'`) would leak between users!

---

## 3. The MRO (Method Resolution Order) Labyrinth

Generic CBVs (`ListView`, `UpdateView`, etc.) rely heavily on multiple inheritance.

```text
UpdateView MRO:
UpdateView -> SingleObjectTemplateResponseMixin -> TemplateResponseMixin -> BaseUpdateView -> ModelFormMixin -> FormMixin -> SingleObjectMixin -> ContextMixin -> ProcessFormView -> View
```

### Execution Flow in `UpdateView` (`POST` request)
1. `dispatch()` routes to `post()`
2. `post()` calls `get_form()`
3. `get_form()` calls `get_form_class()` and `get_form_kwargs()`
4. `get_form_kwargs()` calls `get_object()` to pass the instance to the form
5. If valid, `form_valid()` is called -> `form.save()` -> redirect

---

## 4. Basic vs Production Implementation: Custom Mixins

### Basic Implementation (Flawed)
```python
# Flawed Mixin
class AdminOnlyMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)
```

### Production-Ready Implementation
A production mixin must handle the MRO correctly, avoid hardcoded responses, use proper hooks, and handle Unauthenticated users.

```python
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
import logging

logger = logging.getLogger('django.security')

class TenantAdminRequiredMixin(AccessMixin):
    """
    Production mixin: Checks if user is admin for the current tenant.
    Inherits AccessMixin to utilize handle_no_permission() gracefully.
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
            
        tenant_id = kwargs.get('tenant_id')
        if not request.user.has_tenant_admin_access(tenant_id):
            logger.warning(f"Unauthorized access attempt by {request.user.id} on tenant {tenant_id}")
            raise PermissionDenied("You are not an admin for this tenant.")
            
        return super().dispatch(request, *args, **kwargs)
```

---

## 5. View Decorators vs Mixins vs `method_decorator`

- **FBV Decorator**: `@login_required` wraps the function directly.
- **CBV Mixin**: `LoginRequiredMixin` inherits behavior via MRO.
- **CBV `method_decorator`**: `@method_decorator(login_required, name='dispatch')` converts a function decorator to work on a class method.

**Anti-Pattern**: Using `@login_required` directly on a CBV `dispatch` method without `method_decorator`. It will pass the `self` instance as the request!

```python
# BROKEN
class MyView(View):
    @login_required # Fails: passes `self` to login_required instead of `request`
    def dispatch(self, request, *args, **kwargs): ...

# CORRECT
from django.utils.decorators import method_decorator

@method_decorator(login_required, name='dispatch')
class MyView(View):
    ...
```

---

## 6. Performance Benchmarks

CBVs have a slight overhead due to instantiation and multiple method calls, but it's negligible for network-bound I/O.

| View Type | Overhead per 10k Requests | Memory Footprint | Readability (Simple) | Readability (Complex) |
|-----------|---------------------------|------------------|----------------------|-----------------------|
| FBV       | 10ms                      | Minimal          | Excellent            | Poor (Spaghetti)      |
| CBV (Base)| 15ms                      | Moderate         | Good                 | Good (Organized)      |
| CBV (Gen.)| 25ms                      | High             | Poor (Magic)         | Poor (MRO Hell)       |

---

## 7. Decision Matrix: When to choose which?

| Scenario | Recommendation | Why? |
|----------|----------------|------|
| Simple CRUD on a Model | Generic CBVs (`ListView`, etc.) | Eliminates 90% of boilerplate. |
| Complex multi-form wizard | FBV or specialized library | CBV state management across methods becomes brittle. |
| API Endpoints | DRF/Ninja (Class/Function) | Use framework conventions. DRF uses CBVs extensively. |
| Single-page static render | `TemplateView` | Cleanest declarative syntax. |
| Dashboard with 5 unrelated queries | FBV | Overriding `get_context_data` in CBV is messy here. |

---

## 8. Local vs Production: Common Issues

**🔴 SYMPTOM:** Data from User A appears for User B.
**🔍 CAUSE:** State stored on the CBV class itself instead of `self`.
**🔧 REPRODUCE:**
```python
class BadView(View):
    cached_data = [] # Class attribute! Shared across threads/requests!
    
    def get(self, request):
        self.cached_data.append(request.user.id)
        return JsonResponse({'users': self.cached_data})
```
**🔧 FIX:** Always initialize instance variables in `setup()` or `__init__()`, or avoid state entirely.
```python
class GoodView(View):
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.cached_data = [] # Instance attribute. Safe.
```

## 9. Production Readiness Checklist
- [ ] No mutable data structures (lists, dicts) assigned as class attributes on CBVs.
- [ ] Mixins are placed *before* the base View class in the inheritance list (e.g., `class MyView(AuthMixin, View):`).
- [ ] `super().dispatch()` is called in all custom `dispatch` overrides.
- [ ] Heavy logic in `get_context_data` is optimized to avoid N+1 query problems.
