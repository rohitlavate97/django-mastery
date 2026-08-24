from django.db.models import Sum, F
from .models import Order

def get_optimized_orders():
    """
    Returns a QuerySet of Orders optimized to fetch customer data
    and calculate total_spent in the most efficient way possible.
    """
    return Order.objects.select_related(
        'customer'
    ).prefetch_related(
        'items'
    ).annotate(
        total_spent=Sum(F('items__price') * F('items__quantity'))
    )
