# 07. Managers & Custom QuerySets

## 1. Mental Model
```text
Model.objects ──▶ Manager ──▶ generates ──▶ QuerySet
      │                                       │
      └─ Contains model-level config          └─ Contains query chaining logic
```

## 2. Why It Exists
Fat models lead to unmaintainable spaghetti code. Custom `QuerySet` and `Manager` classes allow encapsulating business logic directly into the ORM layer, making it reusable, chainable, and testable.

## 3. Internal Working
When you call `Model.objects.active()`, the `Manager` delegates the call to the underlying `QuerySet`. By using `QuerySet.as_manager()`, Django dynamically creates a Manager class that copies all public methods of your QuerySet.

## 4. Basic vs 5. Production-Ready
### ❌ Basic
```python
# Logic scattered in views
active_posts = Post.objects.filter(is_deleted=False, status='published')
```

### ✅ Production-Ready
```python
class PostQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_deleted=False)
        
    def published(self):
        return self.filter(status='published')
        
    def with_author_stats(self):
        return self.select_related('author').annotate(
            author_post_count=models.Count('author__posts')
        )

# Use as_manager to bind to the model
class Post(models.Model):
    # ... fields ...
    objects = PostQuerySet.as_manager()
    
# Usage in view: Chainable and Clean
posts = Post.objects.active().published().with_author_stats()
```

## 6. Anti-Patterns: Soft Delete Default Managers
```python
# ❌ TICKING TIME BOMB
class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

class Post(models.Model):
    objects = SoftDeleteManager() # Default manager!
```
**Why this is dangerous**: 
1. The Django Admin will silently hide deleted objects, making restoration impossible via UI.
2. If a `Comment` has a ForeignKey to a deleted `Post`, cascading deletes or related object accesses will throw `DoesNotExist` because the default manager hides it.

**Fix**: Always name custom managers explicitly (e.g., `active_objects`) or override `base_manager_name` and use standard `objects` for all rows.

## 13. Production Checklist
- [ ] Business logic is encapsulated in custom `QuerySet` methods.
- [ ] `QuerySet.as_manager()` is used instead of duplicating methods on Managers.
- [ ] Default manager (`objects`) NEVER filters out rows (e.g., soft deletes).
