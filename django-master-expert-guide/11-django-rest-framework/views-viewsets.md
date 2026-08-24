# Views and ViewSets in Django Rest Framework

## 1. Mental Model: The View Hierarchy

```text
APIView
  └── GenericAPIView (adds queryset, serializer_class, pagination, filtering)
        ├── ListAPIView / CreateAPIView / RetrieveAPIView (Mixins applied)
        └── ViewSetMixin (changes URL routing from .as_view() to Action mapping)
              └── ViewSet (APIView + ViewSetMixin)
              └── GenericViewSet (GenericAPIView + ViewSetMixin)
                    ├── ModelViewSet (CRUD Mixins + GenericViewSet)
                    └── ReadOnlyModelViewSet (Read Mixins + GenericViewSet)
```

## 2. Why It Exists

REST APIs follow predictable patterns (List, Create, Retrieve, Update, Destroy). DRF provides class-based views to abstract these patterns, drastically reducing boilerplate while keeping the flexibility to override anything.

## 3. Decision Matrix: Which one to use?

| Class | When to Use | Trade-offs |
|-------|-------------|------------|
| `APIView` | Complex orchestrations, no direct Model mapping. | Maximum boilerplate, no built-in pagination/filtering. |
| `GenericAPIView` + Mixins | Specific operations on a Model (e.g., just List and Create). | Explicit, very readable, avoids exposing unintended endpoints. |
| `ModelViewSet` | Standard CRUD for a Model. Rapid prototyping. | Easy to accidentally expose destructive operations (e.g., DELETE). |
| `ReadOnlyModelViewSet` | Standard read-only operations (List, Retrieve). | Safe for public endpoints. |

## 4. Production-Ready ModelViewSet Implementation

### Overriding for Security and Tenant Isolation

```python
from rest_framework import viewsets, permissions, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Document
from .serializers import DocumentSerializer, DocumentDetailSerializer

class DocumentViewSet(viewsets.ModelViewSet):
    """
    Production-ready ViewSet demonstrating tenant isolation, 
    dynamic serializers, and action routing.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # 🟢 CRITICAL: Tenant Isolation at the QuerySet level
        # This is strictly better than relying on object-level permissions alone
        return Document.objects.filter(owner=self.request.user)
        
    def get_serializer_class(self):
        # Dynamic serializers based on action
        if self.action == 'retrieve':
            return DocumentDetailSerializer
        return DocumentSerializer
        
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        document = self.get_object()
        document.is_archived = True
        document.save()
        return Response({'status': 'archived'})
```

## 5. Anti-Patterns

### 🔴 Relying purely on `filter_backends` for Security

```python
class UnsafeViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all() # 💣 DANGEROUS
    filter_backends = [MyTenantFilterBackend]
```
If `MyTenantFilterBackend` fails, is misconfigured, or bypassed, users see all invoices! 
Always scope `get_queryset()` to the user/tenant.

## 6. Environment-Specific Behavior
- **Local**: `DEBUG=True` enables the browsable API.
- **Production**: Disable browsable API (`rest_framework.renderers.JSONRenderer` only) for performance and security.

## 7. Production Checklist
- [ ] `get_queryset()` always filters by `request.user` or tenant ID.
- [ ] Unused HTTP methods (like PUT or DELETE) are disabled if not explicitly required.
- [ ] Custom `@action` endpoints have appropriate permission checks.
