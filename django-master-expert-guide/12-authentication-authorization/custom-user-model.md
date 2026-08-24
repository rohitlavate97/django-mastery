# Custom User Model in Django: The Critical First Decision

## 1. Mental Model
```text
[ Django Default User ] 
    ├── username (CharField) 
    ├── email (EmailField - optional)
    ├── first_name, last_name
    └── ...

[ AbstractUser ] -> Extends Default User, keeps fields, lets you add more.
    ├── username (CharField)
    ├── bio (TextField)
    └── date_of_birth (DateField)

[ AbstractBaseUser + PermissionsMixin ] -> Total control, start from scratch.
    ├── id (UUIDField)
    ├── email (EmailField, unique=True, REQUIRED_FIELD)
    ├── password (CharField)
    ├── is_active (BooleanField)
    └── groups, user_permissions (from PermissionsMixin)
```

## 2. Why It Exists
Django provides a built-in `User` model, but it makes assumptions (e.g., `username` is required and unique, `email` is not unique). In modern web applications, using an email address as the primary identifier is standard. If you don't swap out the default user model at the very beginning of your project, doing so later requires complex and dangerous database migrations.

## 3. Internal Working
When Django authenticates a user, it looks up the model specified in `settings.AUTH_USER_MODEL`. 
```python
# django/contrib/auth/__init__.py
def get_user_model():
    """
    Return the User model that is active in this project.
    """
    from django.conf import settings
    from django.apps import apps
    try:
        return apps.get_model(settings.AUTH_USER_MODEL, require_ready=False)
    except ValueError:
        raise ImproperlyConfigured("AUTH_USER_MODEL must be of the form 'app_label.model_name'")
```

## 4. Basic Implementation vs 5. Production-Ready Implementation

### Broken/Basic (Ticking Time Bomb) 🔴
```python
# Ticking Time Bomb: Sticking with default User
from django.contrib.auth.models import User

# Why it's bad:
# - Cannot easily change username to email
# - Migrating away later requires manual schema changes and breaks foreign keys
```

### Production-Ready [DJANGO 6.1+] 🟢
```python
# users/models.py
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email field must be set'))
        email = self.normalize_email(email)
        # Convert email to lowercase for uniqueness
        email = email.lower() 
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('email address'), unique=True, db_index=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email
```
```python
# settings.py
AUTH_USER_MODEL = 'users.CustomUser'
```

## 6. Anti-Patterns
🔴 **Anti-Pattern:** Using `OneToOneField(User)` for profile data instead of `AbstractUser` when you actually need to change auth behavior.
*Why it's bad:* It causes N+1 queries every time you need profile data alongside auth data, and still leaves you with `username` instead of `email` for login.

## 7. Environment-Specific Behavior
| Environment | Behavior |
|-------------|----------|
| Local | SQLite might not enforce constraints exactly like Postgres. |
| Production (Postgres 16+) | Enforces unique constraints strictly. UUID generation is handled efficiently. |

## 8. Local Development Issues
🔴 SYMPTOM: `ValueError: Dependency on app with no migrations: users`
🔍 CAUSE: Circular dependency or missing `__init__.py` in migrations folder when setting up custom user model.
🔧 FIX: Ensure the `users` app is at the top of `INSTALLED_APPS` and make migrations for it first before running global migrations.

## 9. Production Issues
🔴 INCIDENT: **Late Migration to Custom User Model**
- **Severity:** High
- **Investigation:** Team tried to switch to `AUTH_USER_MODEL` midway through the project. Django threw `InconsistentMigrationHistory`.
- **Root Cause:** Django bakes the `auth_user` table into many built-in and third-party app migrations.
- **Fix:** Required dropping the database, or writing complex manual SQL to rename tables and update `django_content_type` and `django_migrations` tables manually.

## 10. Failure Simulation
Change `AUTH_USER_MODEL` in an existing project with migrations applied. Watch `python manage.py migrate` fail catastrophically.

## 11. Decision Matrix
| Need | Choice |
|------|--------|
| Need email as login, want complete control | `AbstractBaseUser` + `PermissionsMixin` |
| Just want to add a few fields (bio, avatar) | `AbstractUser` |
| Using external auth solely (No DB passwords) | Still use `AbstractBaseUser` but remove `set_password` logic. |

## 12. Senior-Level Questions
**Q:** Why do we override `normalize_email` and lowercase the entire email?
**A:** `normalize_email` only lowercases the domain part. But `Foo@example.com` and `foo@example.com` are technically different to the DB, allowing duplicate accounts. Lowercasing the whole string prevents this.

## 13. Production Checklist
- [ ] `AUTH_USER_MODEL` set before the very first migration.
- [ ] `id` uses `UUIDField` to prevent user enumeration attacks.
- [ ] `USERNAME_FIELD` is set to `email`.
- [ ] `EmailField` has `unique=True` and `db_index=True`.
