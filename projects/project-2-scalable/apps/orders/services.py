from django.db import transaction
from .models import Order, OrderItem
from apps.catalog.models import Inventory, Product

class OrderService:
    @staticmethod
    @transaction.atomic
    def place_order(product_id, quantity):
        inventory = Inventory.objects.select_for_update().get(product_id=product_id)
        
        if inventory.stock < quantity:
            raise ValueError("Insufficient stock")
            
        inventory.stock -= quantity
        inventory.save()
        
        product = Product.objects.get(id=product_id)
        order = Order.objects.create(status='CONFIRMED')
        OrderItem.objects.create(order=order, product=product, quantity=quantity)
        
        return order
