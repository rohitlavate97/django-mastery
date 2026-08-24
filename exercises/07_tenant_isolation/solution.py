import contextvars
from django.db import models
from django.core.exceptions import PermissionDenied

# Context variable to hold the current tenant ID
_current_tenant_id = contextvars.ContextVar('current_tenant_id', default=None)

def get_current_tenant_id():
    return _current_tenant_id.get()

def set_current_tenant_id(tenant_id):
    return _current_tenant_id.set(tenant_id)

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant_id = request.headers.get('X-Tenant-ID')
        if not tenant_id:
            # For simplicity, we just skip setting it. In a real app, you might block the request.
            pass
        else:
            token = set_current_tenant_id(tenant_id)
            
        try:
            response = self.get_response(request)
            return response
        finally:
            if tenant_id:
                _current_tenant_id.reset(token)

class TenantAwareQuerySet(models.QuerySet):
    def get_queryset(self):
        qs = super().get_queryset()
        tenant_id = get_current_tenant_id()
        if not tenant_id:
            # We enforce that tenant must be set for tenant-aware models
            raise RuntimeError("Tenant ID is not set in the current context.")
        return qs.filter(tenant_id=tenant_id)

class TenantAwareManager(models.Manager):
    def get_queryset(self):
        tenant_id = get_current_tenant_id()
        if not tenant_id:
            raise RuntimeError("Tenant ID is not set in the current context.")
        return super().get_queryset().filter(tenant_id=tenant_id)

class TenantAwareModel(models.Model):
    tenant_id = models.CharField(max_length=255, db_index=True)
    
    objects = TenantAwareManager()
    
    class Meta:
        abstract = True
