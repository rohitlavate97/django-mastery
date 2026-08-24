import pytest
from apps.orders.services import OrderService
from apps.catalog.models import Product, Category, Inventory

@pytest.mark.django_db
def test_order_concurrency():
    cat = Category.objects.create(name="Test")
    prod = Product.objects.create(category=cat, name="Test Product", price="10.00")
    Inventory.objects.create(product=prod, stock=10)
    
    order = OrderService.place_order(prod.id, 5)
    assert order.status == 'CONFIRMED'
    
    inventory = Inventory.objects.get(product=prod)
    assert inventory.stock == 5
    
    with pytest.raises(ValueError):
        OrderService.place_order(prod.id, 10)
