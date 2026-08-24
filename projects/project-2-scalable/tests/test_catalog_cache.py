import pytest
from apps.catalog.services import CatalogService
from apps.catalog.models import Product, Category, Inventory

@pytest.mark.django_db
def test_cache_aside_with_mutex():
    cat = Category.objects.create(name="Test")
    prod = Product.objects.create(category=cat, name="Test Product", price="10.00")
    Inventory.objects.create(product=prod, stock=100)
    
    # First call - cache miss
    data = CatalogService.get_product_details(prod.id)
    assert data['name'] == "Test Product"
    
    # Modify DB directly
    prod.name = "Changed"
    prod.save()
    
    # Second call - cache hit, should return old data
    data2 = CatalogService.get_product_details(prod.id)
    assert data2['name'] == "Test Product"
