# Staff-Level Django Code Review Checklist

## Mental Model
```text
[ Developer ] -> [ Pull Request ] -> [ Code Review ] -> [ Main Branch ] -> [ Production ]
                                     |
                                     v
                           The Gateway of Quality
                           - Correctness
                           - Performance
                           - Security
                           - Concurrency
                           - Observability
```

## Why It Exists
Code review is not about catching syntax errors (linters do that). It's about catching logical flaws, security vulnerabilities, N+1 queries, race conditions, and architectural missteps before they hit production. A Staff engineer's code review focuses on the "what ifs" and the systemic impacts of a change.

## 1. Correctness & Architecture

### Business Logic Validation
- [ ] Does the code actually solve the business problem described in the ticket?
- [ ] Are edge cases handled? (What if the user is deleted? What if the list is empty? What if the payment fails?)
- [ ] Are we reinventing the wheel? (Could a Django built-in or a stable third-party library do this?)
- [ ] Does the implementation violate the Single Responsibility Principle?
- [ ] Are models acting as god objects? Should logic be moved to services, selectors, or model managers?

### State and Data Integrity
- [ ] Are database constraints used properly? (e.g., `UniqueConstraint`, `CheckConstraint` instead of just application-level validation).
- [ ] Is data deletion handled correctly? (Soft delete vs hard delete, cascading behavior).
- [ ] Are we using transactions for multi-step database writes?

```python
# ❌ Anti-pattern: No transaction for multi-step write
def process_order(order):
    order.status = 'PAID'
    order.save()
    Inventory.objects.decrement(order.item) # If this fails, order is paid but inventory not updated!

# ✅ Production implementation
from django.db import transaction

def process_order(order):
    with transaction.atomic():
        order.status = 'PAID'
        order.save()
        Inventory.objects.decrement(order.item)
```

## 2. Performance (Database & API)

### N+1 Queries
- [ ] Are `select_related()` and `prefetch_related()` used when accessing related objects in a loop or serializer?
- [ ] Is the reviewer checking the generated SQL conceptually?

### Database Indexing
- [ ] Are new fields that are filtered or ordered by indexed?
- [ ] Are we using `db_index=True` on boolean fields where it doesn't make sense (low cardinality)?
- [ ] Are composite indexes created for queries filtering on multiple fields?

### Query Optimization
- [ ] Are we using `.exists()`, `.count()`, `.only()`, `.defer()` appropriately?
- [ ] Are bulk operations used? (`bulk_create`, `bulk_update`)

```python
# ❌ Anti-pattern: Saving in a loop
for item in items:
    item.status = 'PROCESSED'
    item.save()

# ✅ Production implementation: Bulk update
for item in items:
    item.status = 'PROCESSED'
Item.objects.bulk_update(items, ['status'])
```

## 3. Security

### Authentication & Authorization
- [ ] Is the endpoint protected? (`IsAuthenticated`, proper permission classes).
- [ ] Are object-level permissions checked? (Can User A access User B's data?)

```python
# ❌ Anti-pattern: Missing object-level permission
def get_invoice(request, invoice_id):
    invoice = Invoice.objects.get(id=invoice_id)
    return render(request, 'invoice.html', {'invoice': invoice})

# ✅ Production implementation: Checking ownership
def get_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id, user=request.user)
    return render(request, 'invoice.html', {'invoice': invoice})
```

### Injection & XSS
- [ ] Are raw SQL queries avoided? If necessary, are parameters passed safely?
- [ ] Is user input sanitized or properly escaped in templates?
- [ ] Are safe strings used carefully? (`mark_safe` usage must be audited).

### CSRF & Security Headers
- [ ] Are `@csrf_exempt` decorators justified?
- [ ] Are sensitive data explicitly excluded from logs?

## 4. Concurrency & Race Conditions

### Resource Locking
- [ ] Are we updating a row that might be updated concurrently? Use `select_for_update()`.
- [ ] Are F() expressions used for relative updates?

```python
# ❌ Anti-pattern: Race condition prone
wallet = Wallet.objects.get(user=user)
wallet.balance += 10
wallet.save()

# ✅ Production implementation: F() expression
from django.db.models import F
Wallet.objects.filter(user=user).update(balance=F('balance') + 10)
```

## 5. Observability & Reliability

### Logging
- [ ] Are critical business events logged?
- [ ] Are errors logged with stack traces? (`logger.exception`)
- [ ] Is there PII in the logs?

### Metrics & Tracing
- [ ] Should this new flow be timed or counted in Prometheus/Datadog?

### Failure Modes & Resiliency
- [ ] Are third-party API calls wrapped in timeouts?
- [ ] Are retries implemented for transient errors? (e.g., Celery task `autoretry_for`).
- [ ] What happens if the cache is down? Does the application gracefully degrade?

## Production Checklist
- [ ] Migrations are reversible and tested.
- [ ] Heavy migrations (adding columns to huge tables) are done safely (e.g., nullable first, backfill, then constraints).
- [ ] Unit and integration tests cover happy paths, edge cases, and failure modes.
- [ ] CI/CD pipeline passes.
- [ ] Feature flags are used for risky rollouts.
