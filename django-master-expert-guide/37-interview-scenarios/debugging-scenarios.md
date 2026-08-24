# Live Debugging Interview: "Production is Down"

## Mental Model
Live debugging interviews test your grace under fire, your systematic approach to isolating variables, and your knowledge of the Linux/Django/PostgreSQL stack. 

```text
[ Detect ] -> [ Triage (Impact/Scope) ] -> [ Mitigate (Stop the bleeding) ] -> [ Isolate Root Cause ] -> [ Permanent Fix ]
```

## Scenario 1: The "100% CPU" Nightmare

**The Setup:** "You are paged at 2 PM. The Datadog dashboard shows all Gunicorn workers are running at 100% CPU. API latency has spiked from 50ms to 30,000ms (timeout). The database CPU is relatively low (20%). What do you do?"

### Step 1: Initial Investigation (Information Gathering)
**Candidate Actions:**
- Check error rates: Are we returning 500s or just 502/504 (timeouts)?
- Check logs: Are there any infinite loop indicators or specific endpoints throwing errors?
- Look at APM (Application Performance Monitoring): Which endpoint is consuming the time?

**Interviewer Response:** "You see that the `/api/v1/export-users/` endpoint is taking 29 seconds and timing out. Errors are all 504 Gateway Timeouts from Nginx."

### Step 2: Isolation and Root Cause Hypothesis
**Candidate Actions:**
- I know the DB CPU is low, so it's not a slow query locking the DB.
- CPU is spiked on the app servers. This implies a Python-level issue: either a massive loop, loading too much data into memory (triggering garbage collection thrashing), or serialization overhead.
- "I'd look at the code for `/api/v1/export-users/`."

**Interviewer provides code:**
```python
def export_users_view(request):
    users = User.objects.all()
    # Serialize to CSV
    response = HttpResponse(content_type='text/csv')
    writer = csv.writer(response)
    for user in users:
        writer.writerow([user.id, user.email, user.profile.bio])
    return response
```

### Step 3: Identifying the Bug
**Candidate:**
1. **N+1 Query:** `user.profile.bio` triggers a DB query for every single user. However, DB CPU is low. Why?
2. **Memory Exhaustion:** `User.objects.all()` without `iterator()` or pagination loads *all* users into Python memory at once. If the user base recently grew, this will cause the server to swap or spend 100% CPU in garbage collection trying to allocate memory for million ORM objects.

### Step 4: Mitigation and Fix
**Mitigation (Immediate):**
"If the site is completely down, I would restart the Gunicorn workers to clear the blocked queues, and temporarily block traffic to `/api/v1/export-users/` at the Nginx layer so users can use the rest of the app."

**Permanent Fix:**
```python
def export_users_view(request):
    # 1. Use server-side cursors (iterator)
    # 2. Use select_related to fix N+1
    # 3. Only fetch needed fields (values_list is even better for CSV)
    
    response = HttpResponse(content_type='text/csv')
    writer = csv.writer(response)
    
    # Fast, low-memory execution
    users_data = User.objects.select_related('profile').values_list(
        'id', 'email', 'profile__bio'
    ).iterator(chunk_size=2000)
    
    for row in users_data:
        writer.writerow(row)
        
    return response
```
*(Even better answer: "A CSV export for a large table should be moved to a Celery background task and the user notified via email when it's ready, rather than blocking an HTTP worker.")*

## Scenario 2: The Silent Data Corruption

**The Setup:** "A customer complains that their account balance is randomly decreasing. They should have $100, but it shows $90, then $85, with no matching transactions in their history. How do you investigate?"

### The Triage
1. **Scope:** Is it one user or all users? (Let's say multiple users).
2. **Recent Deployments:** Were there any recent code changes touching the billing system?
3. **Database Audit:** Do the transaction logs (if they exist) sum up to the current balance?

### Identifying the Bug
This is a classic **Race Condition** indicator.
"I would search the codebase for anywhere the balance is updated manually."

**Interviewer provides code:**
```python
# tasks.py
def deduct_fee(user_id, amount):
    user = User.objects.get(id=user_id)
    user.balance = user.balance - amount
    user.save()
```

### The Fix
"This is a read-modify-write race condition. If two Celery workers run `deduct_fee` for the same user simultaneously, they both read `$100`. Worker A deducts $5 and saves `$95`. Worker B deducts $10 and saves `$90`. The $5 deduction from Worker A is overwritten and lost."

**Solution:**
```python
from django.db.models import F

def deduct_fee(user_id, amount):
    # F-expression shifts the math to the database layer, which is atomic
    User.objects.filter(id=user_id).update(balance=F('balance') - amount)
```
