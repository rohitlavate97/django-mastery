# Code Review Scenarios: The Messy Truth

## Mental Model
Code review is not about finding typos. It's about finding structural weaknesses, unhandled edge cases, and future performance cliffs. You must read code not just as instructions for the CPU, but as a potential failure mode under stress.

```text
[ PR Submitted ] -> [ Reviewer reads DIFF ] -> [ Mental Execution ] -> [ Identify Flaws ] -> [ Constructive Feedback ]
```

## Scenario 1: The Subtle Over-Fetcher

**Background:** The team is building an API endpoint to list all active courses and the names of the students enrolled in each.

### 🔴 The PR Diff (Submitted by Mid-Level Developer)
```python
# views.py
from rest_framework import generics
from .models import Course
from .serializers import CourseSerializer

class ActiveCourseListView(generics.ListAPIView):
    queryset = Course.objects.filter(is_active=True)
    serializer_class = CourseSerializer

# serializers.py
from rest_framework import serializers

class CourseSerializer(serializers.ModelSerializer):
    enrolled_student_names = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ['id', 'title', 'enrolled_student_names']

    def get_enrolled_student_names(self, obj):
        # Fetching all enrollments, then getting user's name
        return [enrollment.student.get_full_name() for enrollment in obj.enrollments.filter(is_active=True)]
```

### 🔍 Senior Engineer Commentary
**Review Outcome: REQUEST CHANGES**

*Comment on `views.py:7`:*
> "Hey! This looks clean, but we have a classic N+1 query situation here. In the serializer, we're iterating through each course and hitting `obj.enrollments.filter()`. If we have 100 courses, that's 1 query for courses + 100 queries for enrollments. We need to optimize this at the database level."

*Comment on `serializers.py:12`:*
> "Furthermore, inside the list comprehension, we're doing `enrollment.student.get_full_name()`. This triggers *another* query for every single enrollment to fetch the `User` object. If a course has 50 students, that's 50 additional queries *per course*. For 100 courses, we're making 1 + 100 + (100*50) = 5,101 queries for a simple list view. This will instantly melt the database in production."

### 🔧 The Required Fix
```python
# views.py
from django.db.models import Prefetch

class ActiveCourseListView(generics.ListAPIView):
    queryset = Course.objects.filter(is_active=True).prefetch_related(
        Prefetch(
            'enrollments',
            queryset=Enrollment.objects.filter(is_active=True).select_related('student')
        )
    )
    serializer_class = CourseSerializer

# serializers.py
class CourseSerializer(serializers.ModelSerializer):
    enrolled_student_names = serializers.SerializerMethodField()
    # ...
    def get_enrolled_student_names(self, obj):
        # Now uses the prefetched data in memory, no extra DB queries!
        return [enrollment.student.get_full_name() for enrollment in obj.enrollments.all()] 
```

## Scenario 2: The "Just in Case" Exception Handler

**Background:** Adding a background task to process payments via Stripe.

### 🔴 The PR Diff
```python
# tasks.py
import stripe
from celery import shared_task
from .models import Order

@shared_task
def charge_customer(order_id, token):
    try:
        order = Order.objects.get(id=order_id)
        charge = stripe.Charge.create(
            amount=int(order.total * 100),
            currency="usd",
            source=token,
            description=f"Charge for Order {order.id}"
        )
        order.status = 'PAID'
        order.transaction_id = charge.id
        order.save()
    except Exception as e:
        order.status = 'FAILED'
        order.save()
        print(f"Payment failed: {e}")
```

### 🔍 Senior Engineer Commentary
**Review Outcome: REQUEST CHANGES (High Priority)**

*Comment on `tasks.py:12`:*
> "Catching a bare `Exception` here is extremely dangerous. What if `Order.objects.get(id=order_id)` throws `Order.DoesNotExist`? We'll jump to the `except` block, try to execute `order.status = 'FAILED'`, and crash with `UnboundLocalError: local variable 'order' referenced before assignment` because `order` was never created."

*Comment on `tasks.py:15`:*
> "Using `print()` in a Celery task won't give us much visibility in production. Let's use `logger.exception('Payment failed')` so it captures the full stack trace and routes to Sentry."

*Comment on `tasks.py:9`:*
> "What happens if the Stripe API is temporarily down (HTTP 502/503) or times out? Right now, we immediately mark the order as FAILED. We should be using Celery's retry mechanism for transient network errors, catching specific Stripe exceptions (`stripe.error.APIConnectionError`, `stripe.error.RateLimitError`). We should only permanently fail for things like `CardError`."

### 🔧 The Required Fix
```python
import logging
import stripe
from celery import shared_task
from django.db import transaction
from .models import Order

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def charge_customer(self, order_id, token):
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        logger.error(f"Cannot process payment: Order {order_id} not found.")
        return

    try:
        charge = stripe.Charge.create(
            amount=int(order.total * 100),
            currency="usd",
            source=token,
            description=f"Charge for Order {order.id}",
            idempotency_key=f"order_{order.id}" # Prevent double charges
        )
        with transaction.atomic():
            order.status = 'PAID'
            order.transaction_id = charge.id
            order.save()
            
    except (stripe.error.APIConnectionError, stripe.error.RateLimitError) as e:
        logger.warning(f"Transient Stripe error for Order {order_id}. Retrying...")
        self.retry(exc=e, countdown=2 ** self.request.retries)
        
    except stripe.error.CardError as e:
        logger.info(f"Card declined for Order {order_id}: {e.user_message}")
        order.status = 'FAILED'
        order.save()
        
    except Exception as e:
        logger.exception(f"Unexpected error processing payment for Order {order_id}")
        order.status = 'FAILED'
        order.save()
```
