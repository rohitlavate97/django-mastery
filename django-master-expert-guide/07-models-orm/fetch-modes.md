# 07. Fetch Modes [DJANGO 6.1+]

## 1. Mental Model
```text
Legacy Django (Pre-6.x)
Accessing un-fetched relation ──▶ Silent implicit N+1 Query

Django 6.1+ Fetch Modes
FETCH_ONE     ──▶ Legacy behavior (implicit single queries)
FETCH_PEERS   ──▶ Smart batching (implicit IN query for peers)
FETCH_RAISE   ──▶ Hard crash on N+1 (Prevents production performance drops)
```

## 2. Why It Exists
The N+1 query problem is the single biggest performance killer in Django applications. Despite `.select_related()`, developers frequently miss deep relations. Django 6.1 introduces configurable fetching behaviors at the database connection and model level.

## 3. Internal Working
Fetch modes modify the `ForwardManyToOneDescriptor` and `ReverseManyToOneDescriptor`. 
When an attribute is accessed:
1. If cached in `_state.fields_cache`, return it.
2. If `FETCH_RAISE`, raise `django.core.exceptions.RelationNotLoaded`.
3. If `FETCH_PEERS`, inspect the origin `QuerySet` cache, collect all peer IDs, and run a single `IN` query.

## 4. Production-Ready Implementation
### ✅ Enforcing FETCH_RAISE in Development
In `settings.py`:
```python
# Force developers to use select_related/prefetch_related natively!
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'prod_db',
        # DJANGO 6.1+ configuration
        'OPTIONS': {
            'fetch_mode': 'FETCH_RAISE', 
        }
    }
}
```

### ✅ Using FETCH_PEERS (Automatic N+1 fix)
```python
class Article(models.Model):
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    
    class Meta:
        fetch_mode = models.options.FETCH_PEERS

# Without select_related:
articles = list(Article.objects.all()[:50])

# First iteration access:
print(articles[0].author) 
# FETCH_PEERS triggers!
# Behind the scenes: SELECT * FROM author WHERE id IN (all 50 article author_ids)
# Next 49 iterations hit the cache instantly. 0 extra queries!
```

## 6. Anti-Patterns
*   **Setting `FETCH_RAISE` in Production without testing**: Do not enable this globally in an existing legacy app unless you have 100% test coverage asserting query counts. It will cause 500 errors.
*   **Relying purely on `FETCH_PEERS`**: While it fixes N+1 by batching, it is still inferior to an explicit `select_related` which executes the JOIN in the exact same DB round-trip.

## 8. Debugging
🔴 **SYMPTOM**: `RelationNotLoaded` Exception.
🔍 **CAUSE**: A serializer or template tried to access `book.author.name` but `author` wasn't prefetched, and `FETCH_RAISE` is active.
🔧 **FIX**: Add `.select_related('author')` to the underlying View QuerySet.

## 13. Production Checklist
- [ ] Local and CI environments use `FETCH_RAISE` to catch N+1 queries.
- [ ] Explicit `.select_related()` is still preferred over `FETCH_PEERS`.
- [ ] Third-party packages evaluated for `FETCH_RAISE` compatibility.
