# 07. Relationships in Django

## 1. Mental Model
```text
Table A (Book)  ─────────▶ Table B (Author)
    │                         ▲
    └─ ForeignKey (author_id) ┘
```
Relationships in Django translate directly to Foreign Key constraints in SQL. `related_name` creates a reverse descriptor in Python to fetch referencing objects.

## 2. Why It Exists
Relational databases require normalized structures. Django provides `ForeignKey`, `OneToOneField`, and `ManyToManyField` to manage JOINs, cascaded deletes, and reverse lookups without writing manual SQL.

## 3. Internal Working
When you define a `ForeignKey`, Django adds a `ForwardManyToOneDescriptor` to the class. Accessing `book.author` triggers `QuerySet.get(id=book.author_id)`. Accessing `author.books.all()` triggers `ReverseManyToOneDescriptor`.

## 4. Basic vs 5. Production-Ready Implementation
### ❌ Basic (Dangerous Defaults)
```python
class Post(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE) # Deletes user's posts silently!
```

### ✅ Production-Ready
```python
class Post(models.Model):
    # Use PROTECT to prevent accidental user deletion if they have posts
    user = models.ForeignKey(
        'auth.User', 
        on_delete=models.PROTECT,
        related_name='posts',
        related_query_name='post' # Used in filters: User.objects.filter(post__title='X')
    )
    
    # Custom M2M through model for tracking metadata
    tags = models.ManyToManyField('Tag', through='PostTag')

class PostTag(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    tag = models.ForeignKey('Tag', on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['post', 'tag'], name='unique_post_tag')
        ]
```

## 6. Anti-Patterns
*   **Implicit M2M tables**: Using `models.ManyToManyField('Tag')` without a `through` model means you cannot track *when* the tag was added or *who* added it. Always use explicit `through` models for production entity relations.
*   **Blanket CASCADE**: `on_delete=models.CASCADE` is a ticking time bomb. A rogue script deleting a Category can wipe out 100,000 Products. Use `models.PROTECT` or `models.RESTRICT`.

## 8. Debugging
🔴 **SYMPTOM**: Querying `user.posts.all()` generates N queries.
🔍 **CAUSE**: Missing `prefetch_related` on the reverse descriptor.
🔧 **FIX**: `users = User.objects.prefetch_related('posts')`

## 9. Production Issues
🔴 **INCIDENT**: Deadlocks on M2M insertions.
*   **Investigation**: Two transactions were attempting to insert into the implicit M2M table in different orders.
*   **Fix**: Explicitly sorted the PKs before bulk inserting into the `through` model.
