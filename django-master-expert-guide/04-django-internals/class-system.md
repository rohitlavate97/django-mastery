# Django Class System & Metaclasses [DJANGO 6.1+]

## 1. Mental Model
```text
[Metaclass: ModelBase] 
        | (intercepts class creation)
        v
[Class: MyModel(models.Model)] 
        | (extracts Field attributes -> adds them to _meta)
        | (replaces Field attributes with DeferredAttribute descriptors)
        v
[Instance: my_model_instance]
```

## 2. Why It Exists
Django's declarative API (like Models and Forms) requires magic to turn class-level attributes (Fields) into complex instance-level behavior (DB queries, validation) transparently. Metaclasses power this.

## 3. Internal Working
Trace of `django/db/models/base.py`:
```python
class ModelBase(type):
    def __new__(cls, name, bases, attrs, **kwargs):
        super_new = super().__new__
        new_class = super_new(cls, name, bases, {'__module__': attrs.pop('__module__')})
        
        # Setup _meta (Options class)
        meta = attrs.pop('Meta', None)
        new_class.add_to_class('_meta', Options(meta, app_label))
        
        # Add fields
        for obj_name, obj in attrs.items():
            new_class.add_to_class(obj_name, obj)
            
        return new_class

    def add_to_class(cls, name, value):
        if hasattr(value, 'contribute_to_class'):
            value.contribute_to_class(cls, name)
        else:
            setattr(cls, name, value)
```

## 4. Basic Implementation
```python
from django.db import models

class Person(models.Model):
    name = models.CharField(max_length=100)
```

## 5. Production-Ready Implementation
```python
from django.db import models

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True  # Tell ModelBase NOT to create a DB table for this

class Product(TimeStampedModel):
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
```

## 6. Anti-Patterns
🔴 **TICKING TIME BOMB**: Mutating class attributes in an instance method.
```python
class MyModel(models.Model):
    tags = [] # Shared across ALL instances!

    def add_tag(self, tag):
        self.tags.append(tag) # Memory leak / Data corruption across requests
```

## 7. Environment-Specific Behavior
Metaclass evaluation happens entirely at module import time (startup). There is zero runtime overhead per-request, making it extremely fast in all environments.

## 8. Local Development Issues
🔴 SYMPTOM: `TypeError: Model class module.Model doesn't declare an explicit app_label`
🔍 CAUSE: A model is defined outside an app directory and Django's registry cannot infer its `app_label`.
🔧 FIX: Add `app_label = 'my_app'` inside the model's `Meta` class.

## 9. Production Issues
INCIDENT: Server hang during model definition.
SEVERITY: Low
CAUSE: A developer put a heavy DB query inside a model's class-level attribute (e.g. `default=get_expensive_data()`). It executed during startup, blocking Gunicorn.
FIX: Always pass callables to defaults: `default=get_expensive_data`.

## 10. Failure Simulation
```python
import pytest
from django.db.models.base import ModelBase

def test_abstract_model_cannot_be_instantiated():
    class AbstractOnly(models.Model):
        class Meta:
            abstract = True
            
    with pytest.raises(TypeError):
        # Django actually allows instantiation of abstract models, 
        # but saving them raises an error!
        obj = AbstractOnly()
        obj.save() # Raises NotImplementedError
```

## 11. Decision Matrix
| Need | Solution |
|------|----------|
| Shared fields (created_at) | Abstract Base Class (`abstract = True`) |
| Shared logic | Mixins (Standard Python class) |
| Different Python behavior, same DB | Proxy Model (`proxy = True`) |

## 12. Senior-Level Questions
**Q: How does `name = CharField()` become a string on the instance?**
A: `CharField.contribute_to_class` replaces the class attribute with a `DeferredAttribute` descriptor. When you access `instance.name`, the descriptor's `__get__` fetches the value from `instance.__dict__`.

## 13. Production Checklist
- [ ] No mutable defaults on class attributes.
- [ ] `abstract = True` used properly to avoid multi-table inheritance joins.
