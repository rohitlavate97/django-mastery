# Blueprint: Project 3 - Enterprise SaaS

## Mental Model
Enterprise SaaS introduces isolation (multi-tenancy), extreme reliability (zero-downtime deploys), and real-time complexity (WebSockets). A bug here doesn't just annoy a user; it leaks data between competing companies.

```text
[ Tenant A ] -> [ Shared DB (Row Level Security) ] <- [ Tenant B ]
                      |
[ Django Tenants ] -- [ WebSockets (Daphne/Channels) ]
```

## 1. Multi-Tenancy Strategy

### The Shared Database / Shared Schema Approach
The most scalable approach for SaaS (e.g., Stripe, Slack) is a single database and schema, isolating data via a `tenant_id` foreign key.

**Anti-Pattern:** Manually filtering `tenant` in every view.
```python
# ❌ High Risk of Data Leakage
def get_invoices(request):
    invoices = Invoice.objects.filter(tenant=request.user.tenant)
    return render(request, 'invoices.html', {'invoices': invoices})
```

**Production Implementation:** `django-tenant-schemas` (Schema isolation) or Global QuerySet filtering via middleware.

*Using Custom Manager for Shared Schema:*
```python
# core/managers.py
from django.db import models
from .middleware import get_current_tenant

class TenantManager(models.Manager):
    def get_queryset(self):
        tenant = get_current_tenant()
        if tenant:
            return super().get_queryset().filter(tenant=tenant)
        return super().get_queryset().none() # Fail closed

# models.py
class Invoice(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    amount = models.DecimalField(...)
    
    objects = TenantManager() # Automatically scoped!
```

## 2. Real-Time Updates (Django Channels)

### WebSockets for Complex Workflows
When a long-running background job (e.g., generating an end-of-year tax report) finishes, you must push that to the client, rather than having the client poll the API.

```python
# consumers.py (ASGI)
import json
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close()
        else:
            self.group_name = f"user_notifications_{self.user.id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Receive message from room group
    async def notify(self, event):
        await self.send(text_data=json.dumps({"message": event["message"]}))

# tasks.py (Celery pushing to Channels)
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def generate_report(user_id):
    # logic...
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_notifications_{user_id}",
        {"type": "notify", "message": "Report is ready!"}
    )
```

## 3. Zero-Downtime Deployment

### The Expand/Contract Pattern
Never rename a column or change its type in a single deployment. It will lock the table or cause existing code to fail before the new code boots.

**Phase 1 (Expand):**
1. Add new column `new_status` (nullable).
2. Deploy code that writes to *both* `old_status` and `new_status`, but reads from `old_status`.
3. Run a background script to backfill `new_status` for old rows.

**Phase 2 (Migrate):**
1. Deploy code that reads from `new_status`.

**Phase 3 (Contract):**
1. Drop `old_status` from Django models (do not run DB migration yet).
2. Deploy code.
3. Run DB migration to actually drop `old_status`.

## 4. Chaos Game Days
Intentionally break things in staging (or production if mature).
- **Test:** Kill the primary database node.
- **Expected:** PgBouncer pauses traffic, replica is promoted within 30 seconds, traffic resumes. No 500s returned to client.
