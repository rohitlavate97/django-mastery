# Exercise 02: ORM Optimization

## Objective
Optimize a Django ORM query that currently suffers from severe N+1 query problems.

## Context
You have a dashboard that displays recent orders, their associated customer information, and calculates the total amount spent for each order (sum of `price * quantity` for all items in the order).

The naive implementation does something like this:
```python
orders = Order.objects.all()
data = []
for order in orders:
    customer_name = order.customer.name # Query 1
    items = order.items.all() # Query 2
    total = sum(item.price * item.quantity for item in items)
    data.append(...)
```
For N orders, this produces 1 + 2N queries.

## Requirements
Implement `get_optimized_orders()` in `solution.py` such that:
1. It retrieves all `Order` objects.
2. It fetches the related `Customer` efficiently.
3. It fetches the related `OrderItem` objects efficiently.
4. It annotates each order with `total_spent`.
5. The entire operation must take exactly **2 SQL queries**, regardless of how many orders or items exist.

## Hints
- `select_related`
- `prefetch_related`
- `annotate` and `Sum` with `F` expressions
