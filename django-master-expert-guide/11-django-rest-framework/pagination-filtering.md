# Pagination and Filtering in DRF

## 1. Pagination Mental Model

```text
Client Request: GET /api/items/?page=50000
      |
      v
Pagination Backend
      |-- PageNumberPagination: Query `OFFSET 499990 LIMIT 10` (SLOW!)
      |-- LimitOffsetPagination: Query `OFFSET X LIMIT Y` (SLOW!)
      |-- CursorPagination: Query `WHERE created_at < 'cursor_val' LIMIT 10` (FAST!)
      v
Paginated Response
```

## 2. Why CursorPagination is Required for Large Datasets

### 🔴 The OFFSET Crash
SQL `OFFSET` requires the database to scan and discard all rows up to the offset before returning the limit.
`OFFSET 1000000 LIMIT 10` will read 1,000,010 rows, causing high CPU and slow responses.

### 🟢 The Cursor Pagination Fix
Cursor pagination uses an indexed column (usually a timestamp) to fetch the next set of rows.

```python
from rest_framework.pagination import CursorPagination

class CreatedAtCursorPagination(CursorPagination):
    page_size = 100
    ordering = '-created_at' # MUST be an indexed column in the DB!
```

## 3. Filtering with `django-filter`

```python
# filters.py
import django_filters
from .models import Product

class ProductFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr='lte')
    category_name = django_filters.CharFilter(field_name='category__name', lookup_expr='iexact')

    class Meta:
        model = Product
        fields = ['category', 'in_stock']

# views.py
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    
    # Apply filtering, searching, and ordering
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_class = ProductFilter
    search_fields = ['name', 'description'] # Uses ILIKE (slow on large text, use Full Text Search instead)
    ordering_fields = ['price', 'created_at']
```

## 4. Search Filter Anti-Patterns
`search_fields = ['name', 'description']` generates `ILIKE` queries in PostgreSQL. For massive tables, this causes sequential scans.
**Fix**: Use PostgreSQL Full-Text Search (e.g., `SearchVectorField`) or dedicated search engines like Elasticsearch/Typesense.

## 5. Production Checklist
- [ ] Offset pagination is disabled for tables > 100k rows; Cursor pagination is used instead.
- [ ] Columns used in `CursorPagination.ordering` have a database index (`db_index=True`).
- [ ] `SearchFilter` is not used on massive text columns without Trigam/FTS indexes.
