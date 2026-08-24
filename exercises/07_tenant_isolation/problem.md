# Exercise 07: Multi-tenant Data Isolation

## The Problem
In a single-database SaaS architecture, data for all tenants (customers) lives in the same tables. Developers must remember to add `.filter(tenant=request.tenant)` to every query. Forgetting this can lead to catastrophic data leakage where one customer sees another customer's data.

## Your Task
Implement a robust multi-tenant data isolation system using Python's `contextvars` to avoid passing the tenant explicitly everywhere.

### Requirements
1. **Context Management**: Use `contextvars.ContextVar` to store the current tenant ID.
2. **Middleware**: Create `TenantMiddleware` to extract the tenant ID from the request (e.g., from a header `X-Tenant-ID`) and set the context variable.
3. **Manager/QuerySet**: Create `TenantAwareQuerySet` and `TenantAwareManager` that automatically apply a `.filter(tenant_id=...)` to every query based on the active context variable.
4. **Safety**: Raise a `RuntimeError` if a query is attempted on a tenant-aware model without an active tenant, unless explicitly bypassed (e.g., for superusers or background tasks).
