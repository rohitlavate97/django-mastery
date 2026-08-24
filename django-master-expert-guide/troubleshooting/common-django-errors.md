# Django Mastery: Common Django Errors & Solutions

Fast lookup for the 25 most frequent Django stack traces.

### 1. `django.core.exceptions.ImproperlyConfigured`
- **Symptom**: App crashes on startup.
- **Cause**: Missing environment variable, or settings variable configured incorrectly.
- **Fix**: Check `settings.py` for variables using `os.environ['X']` where 'X' is not set. Use `env.get('X')` or `django-environ`.

### 2. `django.core.exceptions.AppRegistryNotReady`
- **Symptom**: Crashes during file imports.
- **Cause**: Importing models at the top level of a file that is loaded before Django initializes apps (e.g., inside `apps.py`, `__init__.py`, or custom management command base).
- **Fix**: Move the import inside the function/method, or use `django.apps.apps.get_model()`.

### 3. `django.db.utils.OperationalError: no such table`
- **Symptom**: Fails on DB read/write.
- **Cause**: The migration was created but not applied (`migrate`).
- **Fix**: Run `python manage.py migrate`.

### 4. `django.db.utils.OperationalError: server closed the connection unexpectedly`
- **Symptom**: Random query failures in long-running processes (Celery or background tasks).
- **Cause**: Database connection timed out or was killed by DB server/firewall.
- **Fix**: Close old connections manually `django.db.close_old_connections()` in long scripts, or fix `CONN_MAX_AGE`.

### 5. `django.core.exceptions.FieldError: Cannot resolve keyword 'X' into field.`
- **Symptom**: Crash on QuerySet evaluation.
- **Cause**: Typo in `.filter(X=...)` or attempting to filter across a reverse relation using the wrong `related_query_name`.
- **Fix**: Check model definition. If jumping across relations, use double underscores (`__`).

### 6. `django.db.utils.ProgrammingError: column "X" of relation "Y" does not exist`
- **Symptom**: Production deployment crash.
- **Cause**: Application code looking for a column that hasn't been migrated yet (Code deployed BEFORE database migration).
- **Fix**: Always deploy DB migrations before code, or use Expand/Contract pattern.

### 7. `django.core.exceptions.MultipleObjectsReturned`
- **Symptom**: `.get()` throws an error.
- **Cause**: `.get()` expected exactly 1 row, but the query matched 2 or more.
- **Fix**: Use `.filter().first()` if you just want one, or fix the data constraint to enforce uniqueness.

### 8. `django.core.exceptions.ObjectDoesNotExist` / `Model.DoesNotExist`
- **Symptom**: `.get()` throws an error.
- **Cause**: Query returned 0 rows.
- **Fix**: Wrap in `try/except Model.DoesNotExist` or use `get_object_or_404()` in views.

### 9. `IntegrityError: duplicate key value violates unique constraint`
- **Symptom**: Crash on `.save()` or `.create()`.
- **Cause**: Attempting to insert a row with a value that already exists in a `unique=True` column.
- **Fix**: Catch `IntegrityError` or use `get_or_create()`.

### 10. `IntegrityError: null value in column "X" violates not-null constraint`
- **Symptom**: Crash on `.save()`.
- **Cause**: A required model field was not provided and has no default.
- **Fix**: Provide the field value or add `null=True, blank=True` to the model.

### 11. `ValueError: Cannot assign "<Model>": "Model.field" must be a "<RelatedModel>" instance.`
- **Symptom**: Assigning a foreign key fails.
- **Cause**: You assigned an integer ID to a model object field, e.g., `post.author = 1`.
- **Fix**: Assign the instance `post.author = user_instance`, or assign the ID to the underlying db column `post.author_id = 1`.

*(This document is a living fast-lookup guide. Append new stack traces here as they occur in production.)*
