# 07. Raw SQL in Django

## 1. Mental Model
```text
[ Django ORM ] ──▶ (Limited by abstraction, cross-db compatibility)
       │
[ Model.objects.raw() ] ──▶ Maps raw SQL to model instances
       │
[ connection.cursor() ] ──▶ Pure Python DB-API 2.0, bypasses Django
```

## 2. Why It Exists
The ORM is an abstraction. It covers 95% of use cases. For the remaining 5% (PostgreSQL CTEs, hyper-optimized recursive queries, or complex analytical aggregations), attempting to force the ORM results in unreadable, slow code. Raw SQL provides an escape hatch.

## 3. Internal Working
*   **`.raw()`**: Executes the query and uses `cursor.description` to map returned columns to model fields via `__init__`.
*   **`cursor.execute()`**: Directly interfaces with `psycopg2`/`psycopg3`. Returns tuples.

## 4. Basic vs 5. Production-Ready
### ❌ Basic (SQL INJECTION RISK)
```python
# 🔴 FATAL VULNERABILITY
user_input = request.GET.get('name')
query = f"SELECT * FROM auth_user WHERE username = '{user_input}'"
users = User.objects.raw(query) # Bobby Tables incoming!
```

### ✅ Production-Ready (Parameterized & Safe)
```python
from django.db import connection

def get_complex_report(min_sales):
    # Parameterized query handled safely by DB driver
    sql = """
        WITH SalesCTE AS (
            SELECT user_id, SUM(amount) as total
            FROM sales
            GROUP BY user_id
            HAVING SUM(amount) > %s
        )
        SELECT u.id, u.username, s.total 
        FROM auth_user u
        JOIN SalesCTE s ON u.id = s.user_id
    """
    
    with connection.cursor() as cursor:
        cursor.execute(sql, [min_sales])
        
        # Dictfetchall pattern
        columns = [col[0] for col in cursor.description]
        return [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]
```

## 6. Anti-Patterns
*   **Raw SQL for Basic CRUD**: Bypasses Django signals, `save()` methods, and constraints.
*   **String Interpolation**: Using `f-strings` or `%` formatting in Python before passing to the DB. ALWAYS pass a list as the second argument to `execute()`.

## 8. Debugging
🔴 **SYMPTOM**: Query works in PGAdmin but fails in Django.
🔍 **CAUSE**: Trailing semicolon or missing parameter interpolation mapping.
🔧 **FIX**: Ensure parameterized arrays match the exact number of `%s` placeholders.

## 13. Production Checklist
- [ ] 0% string formatting used for SQL generation.
- [ ] Raw queries are isolated in service functions, not scattered in views.
- [ ] `dictfetchall` pattern used for non-model raw queries to ensure readability.
