#!/usr/bin/env python3
"""
Django Mastery CLI - An Interactive Engineering Companion
"""

import sys
import os
import json
import random
import subprocess
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "django-master-expert-guide"
EXERCISES_DIR = BASE_DIR / "exercises"
FLASHCARDS_FILE = BASE_DIR / "flashcards" / "django_mastery_deck.json"

ANSI_GREEN = "\033[92m"
ANSI_RED = "\033[91m"
ANSI_CYAN = "\033[96m"
ANSI_YELLOW = "\033[93m"
ANSI_BOLD = "\033[1m"
ANSI_RESET = "\033[0m"


def print_banner():
    banner = f"""{ANSI_CYAN}{ANSI_BOLD}
    ===============================================================
    🚀 DJANGO MASTERY - Principal-Level Engineering Companion 🚀
    ===============================================================
    Target: Django 6.1 | Python 3.12+ | PostgreSQL 16+
    {ANSI_RESET}"""
    print(banner)


def cmd_search(args):
    """Search knowledge base for a specific keyword."""
    query = args.query.lower()
    print(f"{ANSI_YELLOW}🔍 Searching knowledge base for: '{query}'...{ANSI_RESET}\n")

    matches = []
    for md_file in DOCS_DIR.glob("**/*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            if query in content.lower():
                rel_path = md_file.relative_to(BASE_DIR)
                count = content.lower().count(query)
                matches.append((rel_path, count))
        except Exception:
            continue

    if not matches:
        print(f"{ANSI_RED}No matching documents found for '{query}'.{ANSI_RESET}")
        return

    matches.sort(key=lambda x: x[1], reverse=True)
    print(f"{ANSI_GREEN}Found {len(matches)} matching documents:{ANSI_RESET}\n")
    for path, count in matches[:15]:
        print(f"  • {ANSI_BOLD}{path}{ANSI_RESET} ({count} matches)")
    print()


def cmd_checklist(args):
    """Display a specific production checklist."""
    checklist_type = args.name.lower()
    checklist_path = DOCS_DIR / "checklists" / f"{checklist_type}.md"

    if not checklist_path.exists():
        avail = [f.stem for f in (DOCS_DIR / "checklists").glob("*.md")]
        print(f"{ANSI_RED}Checklist '{checklist_type}' not found.{ANSI_RESET}")
        print(f"Available checklists: {', '.join(avail)}")
        return

    print(f"{ANSI_GREEN}{ANSI_BOLD}--- {checklist_path.name.upper()} ---{ANSI_RESET}\n")
    print(checklist_path.read_text(encoding="utf-8"))


def cmd_exercise(args):
    """Run tests for a specific hands-on exercise."""
    ex_num = str(args.number).zfill(2)
    matching_dirs = list(EXERCISES_DIR.glob(f"{ex_num}_*"))

    if not matching_dirs:
        print(f"{ANSI_RED}Exercise {args.number} not found under {EXERCISES_DIR}.{ANSI_RESET}")
        return

    target_dir = matching_dirs[0]
    print(f"{ANSI_CYAN}Running tests for {target_dir.name}...{ANSI_RESET}\n")
    subprocess.run(["pytest", str(target_dir), "-v"])


def cmd_flashcards(args):
    """Interactive spaced repetition flashcards."""
    print_banner()
    if not FLASHCARDS_FILE.exists():
        print(f"{ANSI_RED}Flashcards file not found at {FLASHCARDS_FILE}{ANSI_RESET}")
        return

    with open(FLASHCARDS_FILE, "r", encoding="utf-8") as f:
        deck = json.load(f)

    category = args.category.lower() if args.category else None
    cards = [c for c in deck if not category or category in c.get("category", "").lower()]

    if not cards:
        print(f"{ANSI_RED}No flashcards found for category: {args.category}{ANSI_RESET}")
        return

    random.shuffle(cards)
    print(f"{ANSI_GREEN}Starting flashcard review session ({len(cards)} cards)...{ANSI_RESET}")
    print(f"Press Enter to reveal the answer, and rate your confidence (1=Hard, 2=Good, 3=Easy, q=Quit)\n")

    for i, card in enumerate(cards, 1):
        print(f"{ANSI_BOLD}[Card {i}/{len(cards)}] - Category: {card['category']}{ANSI_RESET}")
        print(f"\n{ANSI_YELLOW}Q: {card['question']}{ANSI_RESET}\n")
        cmd = input(f"{ANSI_CYAN}[Press Enter to see answer (or 'q' to exit)]{ANSI_RESET} ")
        if cmd.strip().lower() == "q":
            break

        print(f"\n{ANSI_GREEN}A:\n{card['answer']}{ANSI_RESET}\n")
        print("-" * 60)


def cmd_incident(args):
    """Interactive production outage triage simulation."""
    print_banner()
    print(f"{ANSI_RED}{ANSI_BOLD}🚨 [INCIDENT SIMULATION - 02:15 AM]{ANSI_RESET}")
    print(f"{ANSI_YELLOW}Alert: Datadog reporting API error rate jumped to 14.8%. Status: P1 SEV.{ANSI_RESET}")
    print(f"Symptoms: Nginx returning 502 Bad Gateway intermittently. PostgreSQL CPU is at 98%.\n")

    steps = [
        ("Step 1: What is your immediate first triage action?",
         [
             "A) Restart the PostgreSQL database server immediately",
             "B) Check `pg_stat_activity` for active queries and lock contention",
             "C) Scale Gunicorn workers from 4 to 32 on all web instances",
             "D) Flush the entire Redis cache cluster"
         ],
         "B",
         "Checking `pg_stat_activity` allows you to see active queries causing 98% CPU before restarting or worsening connection exhaustion."),
        ("Step 2: `pg_stat_activity` shows 80 connections waiting on `SELECT ... FOR UPDATE` on table `inventory_item`. What is the root cause?",
         [
             "A) Deadlock / high-contention row lock held by long-running transactions",
             "B) Corrupted PostgreSQL WAL files",
             "C) Nginx proxy buffer overflow",
             "D) Missing index on `inventory_item.id`"
         ],
         "A",
         "High-contention row locks from uncommitted long-running transactions cause waiting workers to exhaust the database connection pool."),
        ("Step 3: What is the correct immediate mitigation to restore service without data loss?",
         [
             "A) Terminate the blocking PID with `pg_terminate_backend(pid)` and enable temporary rate limiting on the checkout endpoint",
             "B) Drop table `inventory_item` and re-run migrations",
             "C) Set `CONN_MAX_AGE = None` in Django settings",
             "D) Turn off `transaction.atomic()` globally"
         ],
         "A",
         "Terminating the blocking backend releases waiting workers immediately, while rate limiting prevents a recurring stampede.")
    ]

    score = 0
    for q_title, options, correct, explanation in steps:
        print(f"\n{ANSI_BOLD}{q_title}{ANSI_RESET}")
        for opt in options:
            print(f"  {opt}")
        ans = input(f"\n{ANSI_CYAN}Choose action (A/B/C/D): {ANSI_RESET}").strip().upper()
        if ans == correct:
            print(f"{ANSI_GREEN}✅ Correct Decision!{ANSI_RESET} {explanation}")
            score += 1
        else:
            print(f"{ANSI_RED}❌ Suboptimal Action.{ANSI_RESET} Correct: {correct}. {explanation}")

    print(f"\n{ANSI_BOLD}Simulation Complete. Score: {score}/{len(steps)}{ANSI_RESET}")
    if score == 3:
        print(f"{ANSI_GREEN}🏅 Excellent on-call incident response leadership!{ANSI_RESET}")
    else:
        print(f"{ANSI_YELLOW}📖 Review `20-debugging/runbooks/502-errors.md` and `10-transactions-concurrency/deadlocks.md`.{ANSI_RESET}")


def cmd_assess(args):
    """Interactive self-assessment against the mastery rubric."""
    print_banner()
    print(f"{ANSI_YELLOW}{ANSI_BOLD}Self-Assessment Quiz: Test Your Django Engineering Depth{ANSI_RESET}\n")

    questions = [
        ("1. What happens internally when `transaction.atomic()` is nested?",
         "A) A new database transaction BEGINs\nB) A SAVEPOINT is created\nC) Queries execute with autocommit\nD) A table lock is acquired",
         "b",
         "Django uses database SAVEPOINTs for nested atomic blocks, releasing or rolling back to the savepoint on exit."),
        ("2. Why can accessing a ForeignKey field on a Model instance trigger an unexpected SQL query?",
         "A) Model fields are descriptors (DeferredAttribute/ForwardManyToOneDescriptor)\nB) Django reloads the model from database on access\nC) Python metaclasses evaluate fields lazily\nD) Signals trigger DB lookups",
         "a",
         "ForeignKey fields are descriptors that lazy-load related instances if not prefetched via `select_related()`."),
        ("3. In PostgreSQL + Django, which isolation level is the default?",
         "A) Read Uncommitted\nB) Read Committed\nC) Repeatable Read\nD) Serializable",
         "b",
         "PostgreSQL defaults to Read Committed isolation, meaning transactions only see committed changes."),
        ("4. When should Celery tasks be enqueued inside a database transaction?",
         "A) Inside the atomic block\nB) Inside `transaction.on_commit()` callback\nC) In a post_save signal without on_commit\nD) In custom middleware",
         "b",
         "`transaction.on_commit()` guarantees the worker only processes the task AFTER the database row has committed."),
        ("5. In Django 6.1, what does `FETCH_RAISE` do?",
         "A) Fetches all related peers in a batch\nB) Throws an exception if a non-prefetched relation is accessed\nC) Raises connection timeout limits\nD) Retries failed SQL queries automatically",
         "b",
         "`FETCH_RAISE` eliminates implicit N+1 queries by raising an exception whenever code accesses related data that was not explicitly prefetched.")
    ]

    score = 0
    for idx, (q, choices, ans, explanation) in enumerate(questions, 1):
        print(f"{ANSI_BOLD}{q}{ANSI_RESET}")
        print(choices)
        user_ans = input(f"\n{ANSI_CYAN}Your answer (A/B/C/D): {ANSI_RESET}").strip().lower()
        if user_ans == ans:
            print(f"{ANSI_GREEN}✅ Correct!{ANSI_RESET} {explanation}\n")
            score += 1
        else:
            print(f"{ANSI_RED}❌ Incorrect.{ANSI_RESET} Correct answer: {ans.upper()}. {explanation}\n")

    print(f"{ANSI_BOLD}--------------------------------------------------{ANSI_RESET}")
    print(f"Your Score: {score}/{len(questions)} ({score/len(questions)*100:.0f}%)")
    if score == 5:
        print(f"{ANSI_GREEN}{ANSI_BOLD}🏆 Outstanding! You have Staff/Principal level Django instincts.{ANSI_RESET}")
    elif score >= 3:
        print(f"{ANSI_YELLOW}👍 Solid intermediate/advanced grasp. Review the Internals & Concurrency sections to reach mastery.{ANSI_RESET}")
    else:
        print(f"{ANSI_RED}📖 Start with `00-learning-system` and `04-django-internals` to build foundational mental models.{ANSI_RESET}")


def main():
    parser = argparse.ArgumentParser(
        description="Django Mastery CLI - Interactive Engineering Companion",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # search command
    p_search = subparsers.add_parser("search", help="Search the 38-section knowledge base")
    p_search.add_argument("query", help="Keyword or topic to search for")

    # checklist command
    p_check = subparsers.add_parser("checklist", help="View production readiness checklists")
    p_check.add_argument("name", help="Checklist name (e.g. pre-deployment, security-audit, migration-safety)")

    # exercise command
    p_ex = subparsers.add_parser("exercise", help="Run automated test suite for an exercise")
    p_ex.add_argument("number", type=int, help="Exercise number (1 through 10)")

    # flashcards command
    p_fc = subparsers.add_parser("flashcards", help="Interactive active-recall spaced repetition review")
    p_fc.add_argument("--category", help="Filter flashcards by category", default=None)

    # incident command
    subparsers.add_parser("incident", help="Interactive 2 AM production incident triage simulation")

    # assess command
    subparsers.add_parser("assess", help="Take an interactive self-assessment quiz")

    args = parser.parse_args()

    if not args.command:
        print_banner()
        parser.print_help()
        return

    if args.command == "search":
        cmd_search(args)
    elif args.command == "checklist":
        cmd_checklist(args)
    elif args.command == "exercise":
        cmd_exercise(args)
    elif args.command == "flashcards":
        cmd_flashcards(args)
    elif args.command == "incident":
        cmd_incident(args)
    elif args.command == "assess":
        cmd_assess(args)


if __name__ == "__main__":
    main()
