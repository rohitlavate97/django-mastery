# Django Fundamentals: Management Commands

## 1. Mental Model: Management Commands

Management commands are Django's CLI interface. They allow you to interact with the Django application context (database, settings, models) from the terminal, outside the HTTP request-response cycle.

```text
+-------------------------------------------------------------+
|                     DJANGO CLI                              |
|                                                             |
|  $ python manage.py <command_name> <arguments>              |
|                                                             |
|  +--------------------------------------------------------+ |
|  | BaseCommand Subclass                                   | |
|  | - add_arguments()  # Parses CLI args                   | |
|  | - handle()         # Executes logic                    | |
|  +--------------------------------------------------------+ |
|             |                            |                  |
|        [ Models ]                   [ Services ]            |
|             |                            |                  |
|        [ Database ]                 [ External APIs ]       |
+-------------------------------------------------------------+
```

### Why It Exists
You need a way to run background tasks, execute one-off scripts, perform database migrations, and handle cron jobs with full access to Django's ORM and settings.

---

## 2. Built-in Commands Deep Dive

### `runserver`
- **What it does**: Starts a lightweight development web server.
- **Internals**: Spawns two threads/processes. One watches files for changes, the other runs the server. If a file changes, the watcher restarts the server.
- **Why NEVER in production**: It is single-threaded, has zero security auditing, and handles static files inefficiently. Use Gunicorn/uWSGI instead.

### `makemigrations` & `migrate`
- `makemigrations`: Inspects your models and compares them against the current state of migration files, generating new ones.
- `migrate`: Synchronizes the database state with the current set of models and migrations. It tracks applied migrations in the `django_migrations` table.

### `collectstatic`
- **What it does**: Copies static files from all your apps and specific directories into `STATIC_ROOT`.
- **Production usage**: Crucial step in the CI/CD pipeline or Docker build process. Production web servers (Nginx) serve from `STATIC_ROOT`.

### `check --deploy`
- Runs a suite of system checks. The `--deploy` flag specifically checks for production misconfigurations (e.g., `DEBUG=True`, missing secure cookies).

### `dumpdata` & `loaddata`
- **What they do**: Export and import database data in JSON/XML format.
- **Pro-tip**: Use `--natural-foreign` and `--natural-primary` to avoid hardcoded ID conflicts when moving data between environments.

---

## 3. Writing Custom Management Commands

Commands must be placed in an app's `management/commands/` directory.

### Basic Implementation

```python
# users/management/commands/deactivate_users.py
from django.core.management.base import BaseCommand
from users.models import User
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'Deactivates users who have not logged in for 90 days'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', 
            type=int, 
            default=90, 
            help='Number of days of inactivity'
        )
        # Boolean flag
        parser.add_argument(
            '--dry-run', 
            action='store_true', 
            help='Run without modifying database'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        cutoff = timezone.now() - timedelta(days=days)
        users = User.objects.filter(last_login__lt=cutoff, is_active=True)
        
        count = users.count()
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f"DRY RUN: Would deactivate {count} users."))
            return

        users.update(is_active=False)
        self.stdout.write(self.style.SUCCESS(f"Successfully deactivated {count} users."))
```

### Production-Ready Implementation (Error Handling & Transactions)
Long-running commands need transactions, logging, and progress reporting.

```python
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from billing.services import process_monthly_billing

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Process monthly billing for active subscriptions'

    def handle(self, *args, **options):
        logger.info("Starting monthly billing process")
        
        try:
            # Wrap in transaction if entire process must succeed or fail together
            with transaction.atomic():
                process_monthly_billing()
                
            self.stdout.write(self.style.SUCCESS("Billing processed successfully"))
        except Exception as e:
            logger.exception("Critical error during billing process")
            self.stderr.write(self.style.ERROR(f"Failed: {str(e)}"))
            # Exit with non-zero code for Cron/Kubernetes to detect failure
            import sys
            sys.exit(1)
```

---

## 4. Production Usage & Anti-Patterns

### Anti-Pattern: No Output / Silent Failures
Commands run by cron jobs must output logs and exit with non-zero codes on failure. If a command catches an exception and just `return`s or `print`s without `sys.exit(1)`, Kubernetes/Cron thinks it succeeded.

### Anti-Pattern: Memory Leaks in Bulk Processing
🔴 **SYMPTOM**: A command processing 1,000,000 rows gets OOM killed.
🔍 **CAUSE**: `QuerySet.iterator()` was not used, loading all 1,000,000 rows into RAM.
🔧 **FIX**: Use `.iterator(chunk_size=2000)` and `bulk_update()`.

### Local Development Issues: Unrecognized Command
🔴 **SYMPTOM**: `Unknown command: 'my_command'`
🔍 **CAUSE**: 
1. The app containing the command is missing from `INSTALLED_APPS`.
2. The `__init__.py` files are missing in `management/` or `management/commands/`.
🔧 **FIX**: Add `__init__.py` files and ensure app is installed.

---

## 5. Senior-Level Questions

**Q: Can I call management commands from inside my Python code?**
A: Yes, using `django.core.management.call_command()`. This is incredibly useful for testing your commands in pytest.
```python
from django.core.management import call_command
from io import StringIO

def test_my_command():
    out = StringIO()
    call_command('deactivate_users', '--days=30', stdout=out)
    assert 'Successfully deactivated' in out.getvalue()
```

**Q: How do I handle command interruption (Ctrl+C or SIGTERM from Kubernetes)?**
A: Django commands don't handle graceful shutdown by default. If running in K8s, implement a signal handler (e.g., catching `signal.SIGTERM`) to cleanly break loops and finish processing the current chunk before exiting.

## 6. Production Readiness Checklist

- [ ] Command implements standard Python `logging`.
- [ ] `sys.exit(1)` is called on critical failures.
- [ ] Large queries use `.iterator()`.
- [ ] Database modifications are wrapped in `transaction.atomic()` where appropriate.
- [ ] `add_arguments` provides a `--dry-run` option for destructive actions.
