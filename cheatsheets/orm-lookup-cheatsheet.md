# Django ORM & QuerySet Syntax Cheat Sheet

## 1. Complex Lookups with `Q()` Objects
```python
from django.db.models import Q

# AND: Implicit or explicit &
Product.objects.filter(Q(price__gte=100) & Q(is_active=True))

# OR: Pipe operator |
User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))

# NOT: Inversion operator ~
Order.objects.filter(~Q(status="CANCELLED"))

# Dynamic Query Building with reduce
from functools import reduce
import operator

filters = [Q(category="electronics"), Q(price__lt=500), Q(stock__gt=0)]
Product.objects.filter(reduce(operator.and_, filters))
```

---

## 2. Database-Level Operations with `F()` Expressions
```python
from django.db.models import F

# Atomic increment (avoids read-modify-write race conditions)
Product.objects.filter(id=product_id).update(stock=F("stock") - 1)

# Cross-field comparisons
Order.objects.filter(actual_delivery__gt=F("estimated_delivery"))

# Sorting with NULLS LAST
Product.objects.order_by(F("discount_price").asc(nulls_last=True))
```

---

## 3. Conditional Expressions with `Case` & `When`
```python
from django.db.models import Case, When, Value, CharField, IntegerField

Order.objects.annotate(
    priority_level=Case(
        When(total_amount__gte=1000, then=Value("VIP")),
        When(total_amount__gte=500, then=Value("HIGH")),
        default=Value("STANDARD"),
        output_field=CharField(),
    )
)
```

---

## 4. Correlated Subqueries with `Subquery` & `OuterRef`
```python
from django.db.models import Subquery, OuterRef

# Get latest order date for each customer without JOIN
latest_order = Order.objects.filter(
    customer=OuterRef("pk")
).order_by("-created_at").values("created_at")[:1]

Customer.objects.annotate(last_order_at=Subquery(latest_order))
```

---

## 5. Efficient Existence with `Exists()`
```python
from django.db.models import Exists, OuterRef

unpaid_orders = Order.objects.filter(customer=OuterRef("pk"), status="PENDING")
Customer.objects.annotate(has_pending_orders=Exists(unpaid_orders))
```

---

## 6. PostgreSQL Window Functions
```python
from django.db.models import Window, F
from django.db.models.functions import RowNumber, Rank, DenseRank, Lead, Lag

# Calculate row rank partitioned by category, ordered by price descending
Product.objects.annotate(
    category_rank=Window(
        expression=Rank(),
        partition_by=[F("category_id")],
        order_by=F("price").desc()
    )
)
```

---

## 7. Django 6.1 Fetch Modes
```python
from django.db.models.enums import FetchMode

# FETCH_RAISE: Throws exception if related object accessed without prefetch (N+1 killer)
Book.objects.prefetch_related("author").fetch_mode(FetchMode.FETCH_RAISE)

# FETCH_PEERS: Batches lookups across sibling instances
Book.objects.fetch_mode(FetchMode.FETCH_PEERS)
```
