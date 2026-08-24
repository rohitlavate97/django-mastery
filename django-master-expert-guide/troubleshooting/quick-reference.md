# Django Mastery: Quick Reference Troubleshooting

Use this matrix to rapidly diagnose system failures.

| 🔴 Symptom / Log Output | 🛠 First Command to Run | 🔍 Likely Subsystem | 🔧 Resolution Path |
|---|---|---|---|
| `OperationalError: FATAL: too many connections` | `psql -c "SELECT count(*) FROM pg_stat_activity;"` | PostgreSQL | Django leaked connections. Tune `CONN_MAX_AGE`, setup PgBouncer. |
| `AppRegistryNotReady: Apps aren't loaded yet.` | `grep -r "import" ./apps/` | Django App Initialization | You imported models at the module level in `__init__.py` or `apps.py` before `django.setup()` finished. Move imports inside methods. |
| `ProgrammingError: relation "x" does not exist` | `python manage.py showmigrations` | Database/Migrations | Missing migration, or code was deployed before migrations were applied. |
| `OperationalError: SSL connection has been closed` | `tail -f /var/log/postgresql/` | DB Network/PgBouncer | Idle connections killed by firewall/load balancer. Lower `CONN_MAX_AGE` below the firewall timeout limit. |
| `100% CPU on Django WSGI workers` | `py-spy top --pid <gunicorn_pid>` | Python / App Code | Regex catastrophic backtracking, massive memory swap, or an infinite loop in a view. |
| `Worker Timeout` in Gunicorn | `grep "Timeout" /var/log/nginx/error.log` | Gunicorn / External API | A downstream API is hanging. Add `timeout=5` to all `requests.get()` calls. |
| Nginx: `502 Bad Gateway` | `systemctl status gunicorn` | WSGI Server | Gunicorn process crashed or failed to bind to the socket. |
| Celery tasks pending but not running | `celery -A proj inspect active` | Celery / RabbitMQ/Redis | Workers are stuck on long-running tasks. Increase concurrency or implement task timeouts. |
| High memory usage out of nowhere | `grep "DEBUG" config/settings.py` | Django Core | `DEBUG = True` is saving all SQL queries to memory (`django.db.connection.queries`). Set `DEBUG=False`. |
| CSRF Verification Failed | Check HTTP headers in browser devtools | Security Middleware | Missing `X-CSRFToken` header in Axios/Fetch call, or secure cookies blocked over HTTP. |
