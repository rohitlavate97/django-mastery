# ORM and Database Debugging

## 1. Mental Model
The Django ORM is an abstraction layer over SQL. Debugging requires bridging the gap between Python code and the actual executed SQL.

## 2. Inspecting Raw SQL
```python
queryset = MyModel.objects.filter(name='test')
print(queryset.query) # Shows the unparameterized SQL
```

## 3. Tracking Query Counts with `assertNumQueries`
Prevent N+1 queries by enforcing query counts in tests.
```python
from django.test import TestCase

class MyTest(TestCase):
    def test_view_queries(self):
        with self.assertNumQueries(4):
            response = self.client.get('/my-view/')
```

## 4. Debugging Execution Plans (EXPLAIN ANALYZE)
Capture the raw query and run it with `EXPLAIN ANALYZE` in psql to see the PostgreSQL query planner's execution path.

```sql
EXPLAIN ANALYZE SELECT * FROM app_mymodel WHERE name = 'test';
```

## 5. Anti-Patterns
🔴 **TICKING TIME BOMB: Unbounded QuerySets**
Iterating over `MyModel.objects.all()` without chunking loads the entire table into memory, leading to an OOM kill.
🔧 **FIX:** Use `.iterator(chunk_size=2000)`.

