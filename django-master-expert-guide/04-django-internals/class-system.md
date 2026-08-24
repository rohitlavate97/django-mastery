# Django Class and Descriptor System

## 1. Mental Model
```text
Metaclass (ModelBase) -> Creates -> Model Class -> Instantiated as -> Model Instance
       |                                |                               |
 Collects Fields                Holds _meta Options            Uses Descriptors to access DB
```

## 2. Why It Exists
Django models abstract the database. Metaclasses allow Django to analyze field definitions at class creation time, build the `_meta` API, and replace class attributes with descriptors (like `DeferredAttribute`) so that instance access triggers data loading.

## 3. Internal Working
1. **ModelBase.__new__**: The metaclass intercepts class creation.
2. **contribute_to_class**: Fields add themselves to the class.
3. **_meta Setup**: The `Options` class (`_meta`) stores fields, indexes, and constraints.
4. **AppRegistry**: Model is registered.

## 4. Basic Implementation
```python
from django.db import models

class Person(models.Model):
    name = models.CharField(max_length=100)
    # Metaclass converts 'name' into a descriptor on the class!
```

## 5. Production-Ready Implementation
```python
from django.db import models

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class Product(TimeStampedModel):
    sku = models.CharField(max_length=50, unique=True)
    
    class Meta:
        db_table = 'inventory_product'
        indexes = [
            models.Index(fields=['sku']),
        ]
```

## 6. Anti-Patterns
🔴 **TICKING TIME BOMB**: Overriding `__init__` incorrectly.
```python
# INCORRECT
class MyModel(models.Model):
    def __init__(self, *args, **kwargs):
        # Missing super()!
        self.custom_attr = True
```

## 7. Environment-Specific Behavior
Model metaclasses run at **import time** (during startup Phase 2). Any failure here crashes the process.

## 8. Local Development Issues
🔴 SYMPTOM: `RuntimeError: Model class doesn't declare an explicit app_label`
🔍 CAUSE: A model is defined outside an app (e.g., in a standalone script) and lacks `app_label` in `Meta`.
🔧 FIX: Add `app_label = 'my_app'` in the `Meta` class.

## 9. Production Issues
INCIDENT: N+1 queries from property access.
SEVERITY: Medium
CAUSE: A standard `@property` accessed a reverse foreign key relation repeatedly.
FIX: Use `cached_property` or prefetch the relation.

## 10. Failure Simulation
```python
# Trying to access _meta fields incorrectly
Product._meta.get_field('invalid_field') # Raises FieldDoesNotExist
```

## 11. Decision Matrix
| Requirement | Solution |
|-------------|----------|
| Share fields across models | Abstract Base Class |
| Change behavior of existing model | Proxy Model |
| Multi-table inheritance | Subclassing concrete model |

## 12. Senior-Level Questions
**Q: How do ForwardManyToOneDescriptor descriptors work?**
A: When you access `book.author`, the descriptor checks its internal cache. If the object isn't there, it executes a SQL query to fetch the author, caches it, and returns it.

## 13. Production Checklist
- [ ] Abstract models explicitly declare `abstract = True`.
- [ ] Proxy models declare `proxy = True`.
- [ ] Avoid heavy logic in model `__init__`.
