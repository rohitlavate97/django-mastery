# Technical Writing for Senior Engineers

## Mental Model
Code solves a problem for a computer today. Technical writing solves a problem for an engineer tomorrow. A Staff engineer writes less code and more documents, aligning dozens of engineers on a single technical direction.

```text
[ Vague Idea ] -> [ RFC (Feedback) ] -> [ Design Doc (Blueprint) ] -> [ ADR (Decision Log) ] -> [ Code ]
```

## 1. Architecture Decision Records (ADRs)

An ADR captures a single, specific architectural decision, the context in which it was made, and its consequences. It prevents the team from re-litigating the same decision 6 months later.

### Standard ADR Template
- **Title:** e.g., "ADR 004: Use Celery for Background Jobs instead of Django-RQ"
- **Status:** Proposed / Accepted / Rejected / Superseded
- **Context:** We are introducing asynchronous processing. We evaluated RQ, Celery, and Huey. Our team has deep Redis experience, but we need advanced workflows (chords, groups) which RQ lacks natively.
- **Decision:** We will adopt Celery with Redis as the broker.
- **Consequences:**
  - *Positive:* Native support for complex workflows, massive community.
  - *Negative:* High operational complexity, configuration footprint is large.

## 2. Request for Comments (RFCs)

RFCs are used to propose a significant change before writing code. The goal is to build consensus and uncover blind spots.

### Key Sections of an RFC
1. **Summary:** 3-sentence elevator pitch.
2. **Motivation:** Why are we doing this *now*? What breaks if we don't?
3. **Proposed Implementation:** How it will work (High-level architecture, DB schema changes).
4. **Drawbacks:** Why should we *not* do this? (If you leave this blank, you haven't thought hard enough).
5. **Alternatives Considered:** What other tools were evaluated and why were they rejected?
6. **Rollout Plan:** Feature flags, data backfills, zero-downtime strategy.

## 3. System Design Documents

A living document that describes how a major component works. This is what you hand to a new hire.

### The "Django Specific" System Doc Checklist
- **Component Diagram:** Mermaid.js or ASCII showing Nginx, Gunicorn, DB, Cache.
- **Data Model:** Core PostgreSQL tables and their relationships.
- **Critical Paths:** Sequence diagrams for the most important user journeys (e.g., Checkout Flow).
- **Failure Modes:** Document what happens if Redis dies, if Stripe API is down, or if the DB runs out of connections.
