# 33 System Design: E-Commerce Backend

## 1. Mental Model
```text
[User] -> [CDN/WAF] -> [API Gateway] -> [Load Balancer]
                                              |
      +-------------------+-------------------+-------------------+
      |                   |                   |                   |
 [Auth Service]    [Cart Service]    [Order Service]   [Inventory Service]
      |                   |                   |                   |
[User DB (PG)]      [Redis Cache]     [Order DB (PG)]    [Redis + PG DB]
                                              |                   |
                                       [Payment Gateway]   [Kafka/RabbitMQ]
```

## 2. Why It Exists
E-commerce backends must handle extreme spikes in traffic (Flash Sales), guarantee strict consistency (no overselling), and process payments reliably without double-charging.

## 3. Internal Working
The hardest part is **Inventory Reservation** and **Payment Reconciliation**.
When a user clicks "Checkout", we must:
1. Lock the inventory.
2. Create an order (Pending).
3. Charge the card.
4. Update order (Success) and finalize inventory OR reverse inventory if payment fails.

## 4. Basic Implementation (Django ORM)
```python
from django.db import transaction

def checkout(user, cart):
    with transaction.atomic():
        # 1. Lock rows
        items = Item.objects.select_for_update().filter(id__in=cart.item_ids)
        
        # 2. Check stock
        for item in items:
            if item.stock < cart.get_quantity(item.id):
                raise OutOfStockError()
                
        # 3. Deduct stock
        for item in items:
            item.stock -= cart.get_quantity(item.id)
            item.save()
            
        # 4. Create Order
        order = Order.objects.create(user=user, total=cart.total)
        
    # 5. Charge Payment (Outside atomic block to prevent long DB locks)
    charge = stripe.Charge.create(amount=order.total, ...)
    return order
```

## 5. Production-Ready Implementation (Redis Lua Script for Flash Sales)
Standard PG locks are too slow for flash sales. We use Redis.
```lua
-- reserve_inventory.lua
local item_key = KEYS[1]
local requested = tonumber(ARGV[1])
local current_stock = tonumber(redis.call('get', item_key) or '0')

if current_stock >= requested then
    redis.call('decrby', item_key, requested)
    return 1 -- Success
else
    return 0 -- Failed
end
```

```python
# Django service
def flash_sale_checkout(user, item_id, quantity):
    # 1. Fast Redis check
    success = redis_client.eval(LUA_SCRIPT, 1, f"stock:{item_id}", quantity)
    if not success:
        raise OutOfStockError()
        
    # 2. Async queue for actual DB update
    create_order_task.delay(user.id, item_id, quantity)
    return "Order processing"
```

## 6. Anti-Patterns
- **Calling Payment Gateway inside `transaction.atomic()`:** If Stripe takes 5 seconds, your row lock in Postgres is held for 5 seconds. Other checkouts will timeout.
- **Floating Point Math for Currency:** `0.1 + 0.2 = 0.30000000000000004`. Use Python's `decimal.Decimal` or store as integer cents.

## 7. Environment-Specific Behavior
| Env | Setup | Notes |
|-----|-------|-------|
| Local | SQLite | Doesn't support `select_for_update` properly. Can mask race conditions. |
| Prod | PostgreSQL | Uses Row-Exclusive Locks. Redis needed for >1000 QPS. |

## 8. Local Development Issues
🔴 **SYMPTOM:** Redis script returns `None` locally.
🔍 **CAUSE:** Local Redis instance has string serialization differently configured, or keys don't exist.
🔧 **FIX:** Initialize Redis keys in a startup script or migration.

## 9. Production Issues
🔴 **INCIDENT:** Users charged, but order remains "Pending".
- **Severity:** CRITICAL
- **Root Cause:** The async task that marks the order as "Success" failed due to a transient DB error.
- **Fix:** Implement a Stripe Webhook endpoint to reconcile state asynchronously, and run a daily cron job to match Stripe charges against PG orders.

## 10. Failure Simulation
Test idempotency by sending the exact same Checkout API request 3 times concurrently. Only one should succeed; others should return the same result or 409 Conflict.

## 11. Decision Matrix
| Lock Strategy | When to use | Max QPS |
|---------------|-------------|---------|
| Optimistic (`version` column) | Low contention (few buyers per item) | High |
| Pessimistic (`select_for_update`) | High contention, strict consistency | ~500 |
| Redis Lua Script | Flash sales, extreme concurrency | >10,000 |

## 12. Senior-Level Questions
**Q: How do you handle idempotency for payments?**
A: Pass an `Idempotency-Key` (e.g., hash of UserID + CartID) to Stripe. Stripe guarantees a key is only charged once per 24 hours.

**Q: What if the Redis node crashes after decrementing stock but before the Celery task is created?**
A: Use the Outbox Pattern or a reliable queue (Kafka). Wrap the Redis decrement and Kafka publish in a distributed transaction, or rely on state reconciliation.

## 13. Production Checklist
- [ ] Price fields use `DecimalField` (Postgres `NUMERIC`).
- [ ] Checkout endpoint uses rate limiting.
- [ ] Idempotency keys are passed to 3rd party payment APIs.
- [ ] Stripe Webhooks are verified with signature checks.
- [ ] Database locks are held for the absolute minimum time possible.
