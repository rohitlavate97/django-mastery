# Code Review Interview Exercises

## Mental Model
In a code review interview, the interviewer hands you a printed sheet or a screen share of a PR diff. They want to see if you catch the systemic issues, the security flaws, and the performance cliffs.

## Exercise 1: The E-Commerce Checkout

**Prompt:** Review this PR for an API endpoint that handles order finalization.

### The Code
```python
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def finalize_order(request, order_id):
    order = Order.objects.get(id=order_id)
    
    if order.status == 'PAID':
        return Response({"error": "Already paid"}, status=400)
        
    # Deduct inventory
    for item in order.items.all():
        product = item.product
        if product.stock < item.quantity:
            return Response({"error": f"Not enough stock for {product.name}"}, status=400)
        product.stock -= item.quantity
        product.save()
        
    # Charge card
    charge_success = PaymentGateway.charge(request.user.card_token, order.total)
    
    if charge_success:
        order.status = 'PAID'
        order.save()
        return Response({"status": "Success"})
    else:
        return Response({"error": "Payment failed"}, status=400)
```

### The Principal-Level Critique

1. **Security (IDOR):** `Order.objects.get(id=order_id)` does not check if the order belongs to `request.user`. A malicious user could pass someone else's order ID and pay for it (or view the error message).
   *Fix:* `get_object_or_404(Order, id=order_id, user=request.user)`

2. **Concurrency (Race Condition):** `product.stock -= item.quantity` is a read-modify-write race condition. If two users check out simultaneously for the last item, both read `stock=1`, both decrement, and stock becomes `-1`.
   *Fix:* Use `select_for_update()` on the product, or use `F('stock') - item.quantity`.

3. **Data Integrity (Transactions):** There is no database transaction. If the order has 3 items, and the first 2 have stock but the 3rd doesn't, the first 2 are deducted, then the view returns a 400 error. The inventory is permanently lost.
   *Fix:* Wrap the entire view logic in `with transaction.atomic():`.

4. **External API in Request Cycle:** `PaymentGateway.charge` is synchronous. If the gateway takes 15 seconds to respond, the Django worker is tied up. If the gateway times out, what happens to the DB transaction?
   *Fix:* Move payment processing to an async Celery task, return a "Processing" status to the client, and use webhooks/polling to update the UI.
