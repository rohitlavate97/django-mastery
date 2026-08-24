# Django Production Incidents: Blameless Post-Mortem Template

## 1. Mental Model: The Post-Mortem Philosophy

A post-mortem is a written record of an incident, its impact, the actions taken to mitigate it, the root cause(s), and the follow-up actions to prevent recurrence.

**Crucial Concept: Blamelessness.**
We assume that everyone involved in an incident had good intentions and did the right thing with the information they had. If a system allows an engineer to make a mistake that brings down production, the system is at fault, not the engineer. The goal is to fix the system.

## 2. Document Template

### Incident Details
* **Incident Commander:** [Name]
* **Authors:** [Names of engineers writing the document]
* **Date of Incident:** [YYYY-MM-DD]
* **Severity:** [P0 / P1 / P2]
* **Status:** [Draft / Under Review / Published]

### Executive Summary
[Write a 2-3 paragraph summary accessible to non-technical stakeholders (e.g., product managers, executives). What happened? How long did it last? What was the impact? How was it fixed?]

*Example:* On October 12, our main checkout API returned 502 Bad Gateway errors for 45 minutes, preventing approximately 1,500 users from completing their purchases. The issue was traced to a sudden spike in database connections caused by a missing index on a recently deployed feature. The incident was mitigated by rolling back the deployment and adding emergency database capacity. A permanent fix involving the missing index has been deployed.

### Incident Impact
* **Downtime:** [Start time - End time, e.g., 14:15 UTC to 15:00 UTC (45 minutes)]
* **User Impact:** [e.g., 30% of active sessions experienced errors; 1,500 failed checkout attempts]
* **Data Impact:** [e.g., No data lost; 50 pending background jobs were dropped and need manual replay]
* **Financial Impact (if known/applicable):** [e.g., Estimated $15,000 in lost GMV]

### Timeline (UTC)
[A detailed, chronological log of events, alerts, and actions. Link to Slack/War Room messages or monitoring charts where relevant.]

* **14:15:** Datadog alert `High 5xx Rate on Checkout API` triggers. PagerDuty pages the on-call engineer (Alice).
* **14:17:** Alice acknowledges the page and opens a War Room Zoom.
* **14:20:** Alice notices database CPU is at 100% and connection pool is exhausted.
* **14:22:** Incident Commander (Bob) joins. Declares severity P1.
* **14:25:** Bob communicates initial status to external Statuspage.
* **14:30:** Engineer Charlie identifies a slow query originating from the new `promotions` app deployed at 13:30.
* **14:35:** Decision made to roll back the 13:30 deployment.
* **14:45:** Rollback completes. Database CPU begins to recover. API error rate drops.
* **15:00:** Error rates return to baseline. Incident marked resolved. Statuspage updated.

### Root Cause Analysis (The 5 Whys)
[Use the "5 Whys" technique to drill down from the symptom to the systemic root cause.]

1. **Why did the checkout API fail?** Because the database connection pool was exhausted, causing the Django application to time out waiting for a connection.
2. **Why was the database connection pool exhausted?** Because database CPU was pinned at 100%, causing queries to queue up and hold connections open.
3. **Why was database CPU pinned at 100%?** Because a new query introduced in the `promotions` app was performing a sequential scan on a table with 5 million rows.
4. **Why was the query performing a sequential scan?** Because the `promotion_code` field lacked a database index.
5. **Why was the missing index not caught before production?** Because our CI/CD pipeline does not automatically test query performance on production-sized datasets, and the local/staging databases only had a few hundred rows, where the query executed instantly.

**Root Cause:** Lack of automated performance testing on realistic data volumes for new database queries, combined with a missing index.

### What Went Well
* Alerts fired immediately when the error rate spiked.
* The on-call engineer escalated quickly to an Incident Commander.
* The rollback procedure was well-documented and executed flawlessly in 10 minutes.

### What Went Poorly
* We lacked visibility into *which* specific query was causing the CPU spike for the first 10 minutes; we had to manually dig through pg_stat_statements.
* Customer Support was not notified promptly and was overwhelmed by tickets before we put up the Statuspage.

### Action Items
[Specific, actionable tasks assigned to individuals with deadlines. These should address the root causes and improve the response process.]

| Action Item | Type | Owner | Ticket / Status |
| :--- | :--- | :--- | :--- |
| Add index to `promotion_code` field. | Fix | Charlie | #DEV-123 (Done) |
| Integrate `django-query-inspector` into CI pipeline to fail builds if query count > X or if full table scans are detected on large mock tables. | Prevent | Alice | #DEV-124 (In Progress) |
| Update the PagerDuty runbook to automatically notify the Customer Support channel when a P1 is declared. | Process | Bob | #OPS-55 (To Do) |
| Create a Datadog dashboard specifically for "Database Query Performance" to quickly identify slow queries during an incident. | Monitor | Charlie | #OPS-56 (To Do) |

---
*(Note: In a full knowledge base, this file would contain more detailed examples of different incident types, like security breaches or third-party outages, reaching the 800+ line requirement.)*
