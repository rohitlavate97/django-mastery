import pytest
from unittest.mock import Mock
from .solution import TenantMiddleware, set_current_tenant_id, get_current_tenant_id, _current_tenant_id, TenantAwareManager, TenantAwareModel
from django.db import models

# A dummy model for testing
class DummyItem(TenantAwareModel):
    name = models.CharField(max_length=255)
    
    class Meta:
        app_label = 'exercises'

@pytest.mark.django_db
def test_tenant_middleware_sets_tenant():
    request = Mock()
    request.headers = {'X-Tenant-ID': 'tenant-123'}
    
    def get_response(req):
        assert get_current_tenant_id() == 'tenant-123'
        return Mock()
        
    middleware = TenantMiddleware(get_response)
    middleware(request)
    
    # Context var should be reset after request
    assert get_current_tenant_id() is None

@pytest.mark.django_db
def test_tenant_aware_manager_raises_error_without_tenant():
    with pytest.raises(RuntimeError, match="Tenant ID is not set"):
        DummyItem.objects.all()

@pytest.mark.django_db
def test_tenant_isolation():
    # Setup data
    token1 = set_current_tenant_id('t1')
    DummyItem.objects.create(tenant_id='t1', name='Item 1')
    _current_tenant_id.reset(token1)
    
    token2 = set_current_tenant_id('t2')
    DummyItem.objects.create(tenant_id='t2', name='Item 2')
    _current_tenant_id.reset(token2)
    
    # Query as t1
    token = set_current_tenant_id('t1')
    items = DummyItem.objects.all()
    assert items.count() == 1
    assert items.first().name == 'Item 1'
    _current_tenant_id.reset(token)
