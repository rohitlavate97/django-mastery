# Enterprise Multi-Tenant SaaS

## Architecture
- Multi-Tenancy model (Shared Database, Shared Schema with Tenant ID isolation).
- Event-Driven Outbox Engine for reliable message delivery.
- Real-Time WebSockets (Django Channels) for tenant-aware push notifications.
- High-Concurrency Inventory Engine using PostgreSQL advisory locks.
- Kubernetes deployment with KEDA autoscaling.

## Multi-Tenancy Model
The multi-tenancy model relies on logical separation (shared schema) using `TenantAwareManager` and context variables (`get_current_tenant()`). 

## WebSocket Testing
Uses `pytest-asyncio` and `Channels` testing communicators to verify WebSocket connection and message delivery with tenant isolation.

## Kubernetes Deployment
Includes manifests for Daphne (ASGI), Celery, Nginx Ingress (with WS support), and KEDA autoscaling.
