from .models import Tenant, TenantDomain
from .context import set_current_tenant, get_current_tenant

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant_id = request.headers.get('X-Tenant-ID')
        tenant = None

        if tenant_id:
            tenant = Tenant.objects.filter(id=tenant_id, is_active=True).first()
        else:
            host = request.get_host().split(':')[0]
            domain = TenantDomain.objects.filter(domain=host).select_related('tenant').first()
            if domain and domain.tenant.is_active:
                tenant = domain.tenant

        if tenant:
            set_current_tenant(tenant)
            request.tenant = tenant
        else:
            set_current_tenant(None)
            request.tenant = None

        response = self.get_response(request)
        set_current_tenant(None)  # cleanup
        return response
