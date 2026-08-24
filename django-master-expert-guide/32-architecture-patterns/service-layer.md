# 32 Architecture Patterns: Service Layer in Django

## 1. Mental Model
```text
[HTTP Request] -> [URL Router] -> [View/API]
                                      |
                                      v
                             [ SERVICE LAYER ] <--- Business Logic Lives Here
                               /      |      \
                              v       v       v
                        [Models]  [Events]  [External APIs]
                           |
                           v
                      [Database]
```
The Service Layer acts as a boundary. Views (which handle HTTP, serialization, and routing) call Services (which handle "what the app actually does"). Models remain pure data structures with ORM capabilities.

## 2. Why It Exists
In standard Django, "Fat Models" or "Fat Views" are common.
- **Fat Views:** Make testing difficult (you have to mock HTTP/Requests).
- **Fat Models:** Couple business logic with database state. When you need to create a User, send a welcome email, and charge a Stripe card, putting this in `User.save()` violates the Single Responsibility Principle and causes side-effects during tests or bulk operations.

## 3. Internal Working (Django Context)
Django's ORM is an implementation of the Active Record pattern. By introducing a Service Layer, we push Django slightly towards Domain-Driven Design (DDD). We decouple the business transaction from the HTTP request cycle.

## 4. Basic Implementation
```python
# services.py
from django.db import transaction
from .models import Order, Product
from .emails import send_order_confirmation

def create_order(user, product_id: int, quantity: int) -> Order:
    """Basic service to create an order."""
    product = Product.objects.get(id=product_id)
    
    with transaction.atomic():
        order = Order.objects.create(
            user=user,
            product=product,
            quantity=quantity,
            total_price=product.price * quantity
        )
        # Deduct inventory
        product.stock -= quantity
        product.save()
        
    send_order_confirmation(user, order)
    return order
```

## 5. Production-Ready Implementation
```python
# services.py
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from typing import Optional
import logging

from .models import Order, Product
from .signals import order_created
from .exceptions import OutOfStockError

logger = logging.getLogger(__name__)

class OrderService:
    @staticmethod
    def create_order(user, product_id: int, quantity: int) -> Order:
        if quantity <= 0:
            raise ValidationError("Quantity must be positive.")
            
        try:
            with transaction.atomic():
                # select_for_update prevents race conditions [POSTGRESQL-ONLY]
                product = Product.objects.select_for_update().get(id=product_id)
                
                if product.stock < quantity:
                    raise OutOfStockError(f"Only {product.stock} left in stock.")
                    
                order = Order.objects.create(
                    user=user,
                    product=product,
                    quantity=quantity,
                    total_price=product.price * quantity
                )
                
                product.stock -= quantity
                product.save(update_fields=['stock'])
                
        except Product.DoesNotExist:
            logger.error(f"Order creation failed: Product {product_id} not found.")
            raise
        except IntegrityError as e:
            logger.error(f"Database integrity error during order creation: {e}")
            raise
            
        # Dispatch event (Signal or Message Queue) AFTER transaction commits
        transaction.on_commit(lambda: order_created.send(sender=OrderService, order=order))
        
        return order
```

## 6. Anti-Patterns (Ticking Time Bombs)
- **God Services:** A `UserService` that handles creation, billing, profile updates, and analytics. 
- **Returning HTTP Responses from Services:** A service should return domain objects or raise exceptions, never a `HttpResponse` or `Response`.
- **Calling Services from Models:** Models should not call services; this creates circular dependencies.

## 7. Environment-Specific Behavior
| Environment | Behavior | Note |
|-------------|----------|------|
| Local (SQLite) | `select_for_update` is ignored | Race conditions won't manifest locally |
| Prod (Postgres)| `select_for_update` locks rows | True concurrency safety |

## 8. Local Development Issues
🔴 **SYMPTOM:** `TransactionManagementError` when testing.
🔍 **CAUSE:** Catching DB exceptions inside an atomic block and continuing to use the transaction.
🔧 **FIX:** Use nested `transaction.atomic()` (savepoints) if you expect and catch database-level exceptions.

## 9. Production Issues
🔴 **INCIDENT:** Deadlocks during high-concurrency checkouts.
- **Severity:** High
- **Investigation:** Two services updated the same tables but in different orders (Order -> Product vs Product -> Order).
- **Root Cause:** Lock acquisition order mismatch.
- **Fix:** Always acquire row locks (`select_for_update`) in a consistent deterministic order (e.g., sorted by ID).

## 10. Failure Simulation
To simulate a race condition locally without `select_for_update`:
```python
import time
def mock_race():
    product = Product.objects.get(id=1)
    time.sleep(2) # Another thread buys the product here
    product.stock -= 1
    product.save()
```

## 11. Decision Matrix
| Approach | When to use | Pros | Cons |
|----------|-------------|------|------|
| Fat Models | Simple CRUD, prototypes | Fast to write | Hard to test side-effects |
| Services | Business apps, SaaS | Testable, clear boundaries | Extra boilerplate |
| CQRS | High scale, complex domains | Read/Write optimization | Extremely complex |

## 12. Senior-Level Questions
**Q: How do you handle pagination in a Service Layer?**
A: Services should return raw QuerySets, not evaluated lists. The View/Controller is responsible for paginating the QuerySet before evaluation.

**Q: Where do permission checks go?**
A: In the View/API layer. The Service assumes the caller is authorized.

## 13. Production Checklist
- [ ] Services do not import from `views.py` or `serializers.py`
- [ ] Database locks (`select_for_update`) are used for inventory/balance mutations
- [ ] Side-effects (emails, analytics) are triggered via `transaction.on_commit()`
- [ ] Domain exceptions (e.g., `InsufficientFunds`) are raised instead of HTTP 400s
