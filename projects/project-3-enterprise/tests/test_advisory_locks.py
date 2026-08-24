import pytest
from django.db import transaction
from apps.inventory.models import Item
from apps.inventory.services import create_reservation, create_reservation_advisory
from apps.tenants.context import set_current_tenant

@pytest.mark.django_db(transaction=True)
def test_advisory_lock_success(tenant):
    set_current_tenant(tenant)
    item = Item.objects.create(tenant=tenant, name="Laptop", stock=10)
    
    from django.db import connection
    if connection.vendor != 'postgresql':
        pytest.skip("Advisory locks only supported on PostgreSQL")
        
    reservation = create_reservation_advisory(item.id, 2, tenant)
    
    item.refresh_from_db()
    assert item.stock == 8
    assert reservation.quantity == 2
