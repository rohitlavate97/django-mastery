# 07. Model Design Patterns in Django

## 1. Mental Model
```text
[ Application Layer ]
       │
       ▼ (Model instantiation, clean(), save())
[ Django ORM Core ] ──▶ Validation (CheckConstraints, UniqueConstraints)
       │
       ▼ (SQL Compiler)
[ Database Layer ]  ──▶ Schema Enforcement (PostgreSQL)
```
Django models bridge Python classes and relational database tables. A robust model design prioritizes **database-level integrity over application-level validation**.

## 2. Why It Exists
Historically, developers relied on `clean()` methods or form validation to enforce business rules. This fails in concurrency (Race Conditions) or bulk operations (e.g., `bulk_create` bypasses `clean()`). Moving logic to constraints and choosing the right fields ensures 100% data integrity at the lowest level.

## 3. Internal Working: Django Field Compilation
When you define `id = models.UUIDField(default=uuid.uuid4)`, Django's metaclass `ModelBase` tracks the order. During migration generation, `Field.db_type()` translates this to PostgreSQL's `uuid`.

## 4. Basic Implementation vs 5. Production-Ready
### ❌ Basic (Anti-Pattern)
```python
class Order(models.Model):
    status = models.CharField(max_length=20) # Magic strings!
    created_at = models.DateTimeField(auto_now_add=True)
```
### ✅ Production-Ready [DJANGO 6.1+]
```python
import uuid
from django.db import models
from django.db.models import CheckConstraint, Q

class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PD', 'Pending'
        SHIPPED = 'SH', 'Shipped'
        DELIVERED = 'DL', 'Delivered'

    # UUIDv7 (if using libraries) or BigAutoField. BigAutoField is best for clustering.
    id = models.BigAutoField(primary_key=True) 
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=2, choices=Status.choices, default=Status.PENDING)
    
    # Django 5+ GeneratedField
    search_vector = models.GeneratedField(
        expression=models.F('status'), # Simplified for example
        output_field=models.CharField(max_length=2),
        db_persist=True
    )

    class Meta:
        constraints = [
            CheckConstraint(
                condition=Q(status__in=Status.values),
                name='valid_order_status'
            )
        ]
```

## 6. Anti-Patterns: Multi-Table Inheritance
```text
🔴 SYMPTOM: Simple queries taking >500ms
🔍 CAUSE: Multi-table inheritance forces a hidden SQL JOIN for every row.
```
```python
# ❌ TICKING TIME BOMB
class Person(models.Model): name = models.CharField(max_length=50)
class Employee(Person): salary = models.IntegerField() # Forces INNER JOIN Person ON Employee.person_ptr_id = Person.id
```
**Fix:** Use Abstract Base Classes (`abstract = True`) or OneToOneField explicitly.

## 7. Environment-Specific Behavior
| Environment | Field Types | Constraints |
|-------------|-------------|-------------|
| SQLite (Local) | JSONField is text-based | Check constraints limited |
| PostgreSQL (Prod)| JSONB native, GinIndex | Full Check/Unique expression support |

## 8. Debugging & 9. Production Issues
🔴 **INCIDENT**: 500 Errors on `bulk_create`
*   **Severity**: High
*   **Investigation**: `clean()` wasn't called. Invalid data entered DB.
*   **Fix**: Migrated app logic to `CheckConstraint`.

## 13. Production Checklist
- [ ] No Multi-Table Inheritance used.
- [ ] Business logic constraints moved to `Meta.constraints`.
- [ ] `TextChoices`/`IntegerChoices` used for all ENUMs.
- [ ] Primary keys reviewed (BigAutoField for performance, UUID for distributed generation).
