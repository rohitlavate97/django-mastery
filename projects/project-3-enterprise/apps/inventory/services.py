from django.db import transaction, connection
from django.db.models import F
from .models import Item, Reservation

def create_reservation(item_id: int, quantity: int, tenant):
    """
    Creates a reservation using PostgreSQL advisory locks for high concurrency,
    fallback to select_for_update for row-level locking.
    """
    with transaction.atomic():
        # Using row-level lock
        item = Item.objects.select_for_update(nowait=True).get(id=item_id, tenant=tenant)
        
        if item.stock >= quantity:
            item.stock = F('stock') - quantity
            item.save(update_fields=['stock'])
            
            reservation = Reservation.objects.create(
                item=item,
                quantity=quantity,
                tenant=tenant
            )
            return reservation
        else:
            raise ValueError("Insufficient stock")

def create_reservation_advisory(item_id: int, quantity: int, tenant):
    """
    Alternative using PostgreSQL advisory locks (xact level).
    """
    lock_id = item_id  # simple mapping
    with transaction.atomic():
        with connection.cursor() as cursor:
            # Wait for exclusive transaction-level lock
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])
            
        item = Item.objects.get(id=item_id, tenant=tenant)
        
        if item.stock >= quantity:
            item.stock = F('stock') - quantity
            item.save(update_fields=['stock'])
            
            reservation = Reservation.objects.create(
                item=item,
                quantity=quantity,
                tenant=tenant
            )
            return reservation
        else:
            raise ValueError("Insufficient stock")
