#!/usr/bin/env python3
"""
Django In-Memory Interactive Sandbox & Profiler

Demonstrates:
1. Dynamic in-memory Django startup with custom models
2. SQL execution inspection via CaptureQueriesContext
3. Real-time comparison of N+1 vs select_related
4. Nested transaction SAVEPOINT mechanics
"""

import os
import sys
import django
from django.conf import settings

# Configure minimal in-memory Django settings
if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY="sandbox-secret-key-for-profiling-and-internals-mastery",
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
        ],
        TIME_ZONE="UTC",
        USE_TZ=True,
    )
    django.setup()

from django.db import models, connection, transaction
from django.test.utils import CaptureQueriesContext

ANSI_GREEN = "\033[92m"
ANSI_RED = "\033[91m"
ANSI_CYAN = "\033[96m"
ANSI_YELLOW = "\033[93m"
ANSI_BOLD = "\033[1m"
ANSI_RESET = "\033[0m"


# Dynamic Models for Profiling
class Author(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()

    class Meta:
        app_label = "auth"


class Article(models.Model):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="articles")
    views_count = models.IntegerField(default=0)

    class Meta:
        app_label = "auth"


def setup_database_schema():
    with connection.schema_editor() as editor:
        editor.create_model(Author)
        editor.create_model(Article)

    # Seed data
    author_a = Author.objects.create(name="Guido van Rossum", email="guido@python.org")
    author_b = Author.objects.create(name="Adrian Holovaty", email="adrian@djangoproject.com")

    for i in range(10):
        Article.objects.create(title=f"Python Article {i}", author=author_a, views_count=100 * i)
        Article.objects.create(title=f"Django Article {i}", author=author_b, views_count=150 * i)


def demo_query_profiling():
    print(f"\n{ANSI_BOLD}1. Profiling N+1 Queries vs `select_related`{ANSI_RESET}")
    print("-" * 60)

    # Scenario A: N+1 queries
    with CaptureQueriesContext(connection) as ctx_n1:
        articles = list(Article.objects.all())
        author_names = [a.author.name for a in articles]

    print(f"  ❌ Naive Loop: {ANSI_RED}{len(ctx_n1)} SQL queries executed{ANSI_RESET}")
    for q in ctx_n1.captured_queries[:3]:
        print(f"     SQL: {q['sql']}")
    print(f"     ... and {len(ctx_n1)-3} more queries.\n")

    # Scenario B: select_related optimization
    with CaptureQueriesContext(connection) as ctx_opt:
        articles_opt = list(Article.objects.select_related("author").all())
        author_names_opt = [a.author.name for a in articles_opt]

    print(f"  ✅ Optimized with `select_related`: {ANSI_GREEN}{len(ctx_opt)} SQL query executed{ANSI_RESET}")
    for q in ctx_opt.captured_queries:
        print(f"     SQL: {q['sql']}")
    print()


def demo_transaction_savepoints():
    print(f"{ANSI_BOLD}2. Inspecting Nested `transaction.atomic()` SAVEPOINT Mechanics{ANSI_RESET}")
    print("-" * 60)

    with CaptureQueriesContext(connection) as ctx_tx:
        with transaction.atomic():
            Author.objects.create(name="Uncle Bob", email="bob@clean-code.com")
            try:
                with transaction.atomic():
                    Author.objects.create(name="Failing Author", email="fail@example.com")
                    raise ValueError("Simulated failure in inner block")
            except ValueError:
                pass  # Inner transaction rolled back to SAVEPOINT

    print(f"  Executed {len(ctx_tx)} SQL statements during atomic block:")
    for q in ctx_tx.captured_queries:
        print(f"     {ANSI_CYAN}{q['sql']}{ANSI_RESET}")

    total_authors = Author.objects.count()
    print(f"\n  Final committed Authors in DB: {ANSI_GREEN}{total_authors}{ANSI_RESET} ('Uncle Bob' preserved, 'Failing Author' rolled back)")


def main():
    print(f"""{ANSI_CYAN}{ANSI_BOLD}
    ===============================================================
    🔬 DJANGO IN-MEMORY INTERACTIVE SANDBOX & SQL PROFILER
    ===============================================================
    Running live in-memory queries and transaction lifecycle tracing
    {ANSI_RESET}""")
    setup_database_schema()
    demo_query_profiling()
    demo_transaction_savepoints()
    print(f"\n{ANSI_GREEN}✅ Sandbox verification complete!{ANSI_RESET}\n")


if __name__ == "__main__":
    main()
