# Behavioral Interview Scenarios for Staff Engineers

## Mental Model
Behavioral interviews at the Staff/Principal level are not about "tell me your biggest weakness." They are about navigating complex human systems, resolving severe technical disputes, managing up, and handling catastrophe with calm leadership.

Use the **STAR** method (Situation, Task, Action, Result) but add an **L** (Learnings) for senior roles.

## Scenario 1: The Architectural Disagreement

**The Question:** "Tell me about a time you strongly disagreed with a peer or a manager on an architectural decision. How did you handle it?"

### What they are evaluating:
- Do you use data or ego to argue?
- Do you understand business trade-offs vs. technical purity?
- Can you "disagree and commit" if the decision doesn't go your way?

### The Principal-Level Response Strategy:
* **Situation:** We needed to build a real-time notification system. Another Senior Engineer wanted to introduce Kafka because "it's web-scale."
* **Task:** I believed Kafka was massive overkill for our current scale (5,000 users) and our team lacked JVM/Zookeeper operational experience.
* **Action:** I didn't attack the technology; I framed it around Operational Cost. I wrote an RFC comparing Kafka vs. Redis Pub/Sub (which we already had in our stack). I highlighted the maintenance hours, CI/CD changes, and hiring requirements for Kafka. I proposed a phased approach: use Redis now behind an interface, swap to Kafka later if throughput hits 10k msgs/sec.
* **Result:** The team aligned on Redis. We shipped in 2 weeks instead of 2 months.
* **Learning:** Always anchor technical debates to business metrics (time-to-market, maintenance cost) rather than technological superiority.

## Scenario 2: The Production Outage

**The Question:** "Describe a time you took down production or were involved in a major outage. How did you react?"

### What they are evaluating:
- Do you panic, or do you have a systematic debugging approach?
- Do you blame others ("QA missed it") or take ownership?
- Do you focus on repairing the *system* (tests, CI) rather than punishing the *human*?

### The Principal-Level Response Strategy:
* **Situation:** A database migration I wrote added a column with a default value to a table with 50 million rows in PostgreSQL.
* **Task:** Upon deployment, the table locked entirely, taking down the main API.
* **Action:** 
    1. *Mitigate:* Immediately alerted the incident channel, rolled back the deployment, and forcefully killed the hung PostgreSQL query via `pg_stat_activity` to release the lock.
    2. *Communicate:* Updated customer support with an ETA.
    3. *Investigate:* Realized that prior to Postgres 11, adding a default value rewrites the entire table.
* **Result:** Downtime was limited to 8 minutes.
* **Learning/Evolution:** We didn't blame anyone; we changed the system. I implemented `django-zero-downtime-migrations` in our CI pipeline to statically analyze migrations and block PRs that attempt table-locking operations. 

## Scenario 3: Mentoring and Leveling Up

**The Question:** "Tell me about a time you mentored a junior or mid-level engineer who was struggling."

### What they are evaluating:
- Empathy and patience.
- Ability to identify root causes of poor performance (is it lack of skill, lack of context, or personal issues?).
- Delegation skills.

### The Principal-Level Response Strategy:
* **Situation:** A mid-level engineer was consistently shipping code with edge-case bugs and their PRs were requiring 4-5 rounds of review.
* **Action:** I noticed their unit tests only covered the "happy path." Instead of nitpicking the PRs, I pair-programmed with them for an hour. I taught them a specific mental model: "Test the edges, not just the center." We built a checklist together for their desk.
* **Result:** Over three months, their defect rate dropped by 60%, and they eventually led a feature launch independently.
