import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from .models import Customer, Order, OrderItem
from .solution import get_optimized_orders
from decimal import Decimal

@pytest.fixture
def setup_data(db):
    c1 = Customer.objects.create(name="Alice", email="alice@example.com")
    c2 = Customer.objects.create(name="Bob", email="bob@example.com")

    for i in range(10):
        o = Order.objects.create(customer=c1 if i % 2 == 0 else c2)
        for j in range(5):
            OrderItem.objects.create(
                order=o,
                product_name=f"Product {j}",
                price=Decimal('10.00'),
                quantity=2
            )

@pytest.mark.django_db
def test_get_optimized_orders(setup_data, django_assert_num_queries):
    # The initial query + prefetch should be exactly 2 queries
    with django_assert_num_queries(2):
        orders = list(get_optimized_orders())
        
        for order in orders:
            # Accessing customer should NOT trigger a query (select_related)
            customer_name = order.customer.name
            
            # Accessing items should NOT trigger a query (prefetch_related)
            items = list(order.items.all())
            
            # Accessing total_spent should NOT trigger a query (annotate)
            assert order.total_spent == Decimal('100.00')  # 5 items * $10 * 2 qty
            
            assert len(items) == 5
            
    assert len(orders) == 10
