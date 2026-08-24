import pytest
from apps.tenants.context import set_current_tenant
from apps.inventory.models import Item

@pytest.mark.django_db
def test_tenant_isolation(tenant, other_tenant):
    # Set context to first tenant
    set_current_tenant(tenant)
    Item.objects.create(tenant=tenant, name="Tenant 1 Item", stock=10)
    
    # Set context to second tenant
    set_current_tenant(other_tenant)
    Item.objects.create(tenant=other_tenant, name="Tenant 2 Item", stock=20)
    
    # Assert isolation
    set_current_tenant(tenant)
    items = Item.objects.all()
    assert items.count() == 1
    assert items.first().name == "Tenant 1 Item"
    
    set_current_tenant(other_tenant)
    items = Item.objects.all()
    assert items.count() == 1
    assert items.first().name == "Tenant 2 Item"
    
    # Cleanup context
    set_current_tenant(None)
    assert Item.objects.all().count() == 2
