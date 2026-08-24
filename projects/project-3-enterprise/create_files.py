import os

BASE_DIR = '/Volumes/Element/Projects/BackEnd/django-mastery/projects/project-3-enterprise'

def write_file(path, content):
    full_path = os.path.join(BASE_DIR, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w') as f:
        f.write(content.strip() + '\n')

files = {
    'pyproject.toml': '''
[tool.poetry]
name = "enterprise-saas"
version = "0.1.0"
description = "Enterprise Multi-Tenant SaaS"
authors = ["Admin <admin@example.com>"]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings"
python_files = ["test_*.py", "*_test.py"]
addopts = "--strict-markers --no-migrations"
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
''',
    'requirements.txt': '''
Django>=5.1,<6.2
djangorestframework>=3.15.0
channels>=4.1.0
channels-redis>=4.2.0
daphne>=4.1.0
psycopg[binary]>=3.1.18
structlog>=24.1.0
pydantic>=2.7.0
pytest>=8.2.0
pytest-asyncio>=0.23.6
pytest-django>=4.8.0
celery>=5.4.0
redis>=5.0.4
PyJWT>=2.8.0
''',
    '.env.example': '''
SECRET_KEY=dev-secret-key
DEBUG=True
DATABASE_URL=postgres://user:password@localhost:5432/enterprise_db
REDIS_URL=redis://localhost:6379/0
''',
    'pytest.ini': '''
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = tests.py test_*.py *_tests.py
addopts = -v --reuse-db
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
''',
    'README.md': '''
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
''',
    'manage.py': '''
#!/usr/bin/env python
import os
import sys

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Couldn't import Django.") from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
''',
    'config/__init__.py': '',
    'config/settings.py': '''
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'unsafe-secret-key')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'channels',
    'apps.tenants',
    'apps.outbox',
    'apps.notifications',
    'apps.inventory',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.tenants.middleware.TenantMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
if os.getenv('DATABASE_URL'):
    import dj_database_url
    DATABASES['default'] = dj_database_url.config(default=os.getenv('DATABASE_URL'))

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.getenv('REDIS_URL', 'redis://localhost:6379/0')],
        },
    },
}

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
''',
    'config/urls.py': '''
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path('admin/', admin.site.urls),
]
''',
    'config/asgi.py': '''
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from apps.notifications.routing import websocket_urlpatterns
from apps.notifications.middleware import JWTAuthMiddlewareStack

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})
''',
    'config/wsgi.py': '''
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
application = get_wsgi_application()
''',
    'apps/tenants/__init__.py': '',
    'apps/tenants/apps.py': '''
from django.apps import AppConfig

class TenantsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tenants'
''',
    'apps/tenants/context.py': '''
from contextvars import ContextVar

_current_tenant = ContextVar("current_tenant", default=None)

def set_current_tenant(tenant):
    return _current_tenant.set(tenant)

def get_current_tenant():
    return _current_tenant.get()
''',
    'apps/tenants/models.py': '''
from django.db import models
from .context import get_current_tenant

class Tenant(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    schema_name = models.CharField(max_length=63, unique=True)
    is_active = models.BooleanField(default=True)
    plan_tier = models.CharField(max_length=50, default='free')

    def __str__(self):
        return self.name

class TenantDomain(models.Model):
    tenant = models.ForeignKey(Tenant, related_name='domains', on_delete=models.CASCADE)
    domain = models.CharField(max_length=255, unique=True)
    is_primary = models.BooleanField(default=True)

    def __str__(self):
        return self.domain

class TenantAwareQuerySet(models.QuerySet):
    def for_current_tenant(self):
        tenant = get_current_tenant()
        if tenant:
            return self.filter(tenant=tenant)
        return self

class TenantAwareManager(models.Manager):
    def get_queryset(self):
        return TenantAwareQuerySet(self.model, using=self._db).for_current_tenant()

class TenantModel(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)

    objects = TenantAwareManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True
''',
    'apps/tenants/middleware.py': '''
from .models import Tenant, TenantDomain
from .context import set_current_tenant, get_current_tenant

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant_id = request.headers.get('X-Tenant-ID')
        tenant = None

        if tenant_id:
            tenant = Tenant.objects.filter(id=tenant_id, is_active=True).first()
        else:
            host = request.get_host().split(':')[0]
            domain = TenantDomain.objects.filter(domain=host).select_related('tenant').first()
            if domain and domain.tenant.is_active:
                tenant = domain.tenant

        if tenant:
            set_current_tenant(tenant)
            request.tenant = tenant
        else:
            set_current_tenant(None)
            request.tenant = None

        response = self.get_response(request)
        set_current_tenant(None)  # cleanup
        return response
''',
    'apps/outbox/__init__.py': '',
    'apps/outbox/apps.py': '''
from django.apps import AppConfig

class OutboxConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.outbox'
''',
    'apps/outbox/models.py': '''
from django.db import models
import uuid

class OutboxMessage(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PUBLISHED', 'Published'),
        ('FAILED', 'Failed'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=255)
    payload = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.event_type} - {self.status}"
''',
    'apps/outbox/services.py': '''
from django.db import transaction
from .models import OutboxMessage

def publish_event(event_type: str, payload: dict):
    """
    Saves the event to the outbox table. Must be called within a transaction
    to guarantee atomicity with business data changes.
    """
    OutboxMessage.objects.create(
        event_type=event_type,
        payload=payload,
        status='PENDING'
    )
''',
    'apps/outbox/relay.py': '''
import time
from django.utils import timezone
from .models import OutboxMessage
import structlog

logger = structlog.get_logger(__name__)

def process_outbox():
    # Fetch pending messages
    messages = OutboxMessage.objects.filter(status='PENDING').order_by('created_at')[:100]
    
    for msg in messages:
        try:
            # Simulate publishing to a message broker (Kafka, RabbitMQ, etc.)
            logger.info("Publishing message", event_type=msg.event_type, msg_id=str(msg.id))
            
            # Update status
            msg.status = 'PUBLISHED'
            msg.published_at = timezone.now()
            msg.save(update_fields=['status', 'published_at'])
            
        except Exception as e:
            logger.error("Failed to publish message", msg_id=str(msg.id), error=str(e))
            msg.status = 'FAILED'
            msg.save(update_fields=['status'])

if __name__ == '__main__':
    while True:
        process_outbox()
        time.sleep(2)
''',
    'apps/notifications/__init__.py': '',
    'apps/notifications/apps.py': '''
from django.apps import AppConfig

class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'
''',
    'apps/notifications/middleware.py': '''
from channels.middleware import BaseMiddleware
from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.conf import settings
import jwt
from urllib.parse import parse_qs

User = get_user_model()

@database_sync_to_async
def get_user_from_token(token):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user = User.objects.get(id=payload['user_id'])
        return user
    except (jwt.InvalidTokenError, User.DoesNotExist, KeyError):
        return AnonymousUser()

class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode('utf-8')
        query_params = parse_qs(query_string)
        
        token = query_params.get('token', [None])[0]
        if token:
            scope['user'] = await get_user_from_token(token)
        else:
            scope['user'] = AnonymousUser()
            
        return await super().__call__(scope, receive, send)

def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(AuthMiddlewareStack(inner))
''',
    'apps/notifications/consumers.py': '''
import json
from channels.generic.websocket import AsyncWebsocketConsumer

class TenantNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        
        # Get tenant_id from URL route kwargs
        self.tenant_id = self.scope['url_route']['kwargs'].get('tenant_id')
        
        if self.user.is_anonymous or not self.tenant_id:
            await self.close()
            return
            
        # Group name specific to tenant and user
        self.group_name = f"tenant_{self.tenant_id}_user_{self.user.id}"
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        pass

    async def tenant_message(self, event):
        message = event["message"]

        await self.send(text_data=json.dumps({
            "message": message
        }))
''',
    'apps/notifications/routing.py': '''
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/notifications/(?P<tenant_id>\\w+)/$', consumers.TenantNotificationConsumer.as_asgi()),
]
''',
    'apps/notifications/services.py': '''
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def send_tenant_notification(tenant_id, user_id, message):
    channel_layer = get_channel_layer()
    group_name = f"tenant_{tenant_id}_user_{user_id}"
    
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "tenant_message",
            "message": message,
        }
    )
''',
    'apps/inventory/__init__.py': '',
    'apps/inventory/apps.py': '''
from django.apps import AppConfig

class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.inventory'
''',
    'apps/inventory/models.py': '''
from django.db import models
from apps.tenants.models import TenantModel

class Item(TenantModel):
    name = models.CharField(max_length=255)
    stock = models.IntegerField(default=0)

    def __str__(self):
        return self.name

class Reservation(TenantModel):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='reservations')
    quantity = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.quantity} of {self.item.name}"
''',
    'apps/inventory/services.py': '''
from django.db import transaction, connection
from django.db.models import F
from .models import Item, Reservation

def create_reservation(item_id: int, quantity: int, tenant):
    """
    Creates a reservation using PostgreSQL advisory locks for high concurrency,
    fallback to select_for_update for row-level locking.
    """
    with transaction.atomic():
        # Using row-level lock
        item = Item.objects.select_for_update(nowait=True).get(id=item_id, tenant=tenant)
        
        if item.stock >= quantity:
            item.stock = F('stock') - quantity
            item.save(update_fields=['stock'])
            
            reservation = Reservation.objects.create(
                item=item,
                quantity=quantity,
                tenant=tenant
            )
            return reservation
        else:
            raise ValueError("Insufficient stock")

def create_reservation_advisory(item_id: int, quantity: int, tenant):
    """
    Alternative using PostgreSQL advisory locks (xact level).
    """
    lock_id = item_id  # simple mapping
    with transaction.atomic():
        with connection.cursor() as cursor:
            # Wait for exclusive transaction-level lock
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])
            
        item = Item.objects.get(id=item_id, tenant=tenant)
        
        if item.stock >= quantity:
            item.stock = F('stock') - quantity
            item.save(update_fields=['stock'])
            
            reservation = Reservation.objects.create(
                item=item,
                quantity=quantity,
                tenant=tenant
            )
            return reservation
        else:
            raise ValueError("Insufficient stock")
''',
    'k8s/deployment-web.yaml': '''
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
      - name: web
        image: enterprise-saas-web:latest
        command: ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: app-secrets
        livenessProbe:
          httpGet:
            path: /admin/login/
            port: 8000
          initialDelaySeconds: 15
          periodSeconds: 20
        readinessProbe:
          httpGet:
            path: /admin/login/
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
''',
    'k8s/deployment-celery.yaml': '''
apiVersion: apps/v1
kind: Deployment
metadata:
  name: celery-worker
spec:
  replicas: 1
  selector:
    matchLabels:
      app: celery-worker
  template:
    metadata:
      labels:
        app: celery-worker
    spec:
      containers:
      - name: celery
        image: enterprise-saas-web:latest
        command: ["celery", "-A", "config", "worker", "-l", "info"]
        envFrom:
        - configMapRef:
            name: app-secrets
''',
    'k8s/ingress.yaml': '''
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web-ingress
  annotations:
    nginx.ingress.kubernetes.io/websocket-services: "web"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.example.com
    secretName: web-tls
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-service
            port:
              number: 8000
''',
    'k8s/configmap-secrets.yaml': '''
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-secrets
data:
  SECRET_KEY: "k8s-secret-key"
  DEBUG: "False"
  DATABASE_URL: "postgres://user:password@db-host:5432/enterprise_db"
  REDIS_URL: "redis://redis-host:6379/0"
''',
    'k8s/keda-scaledobject.yaml': '''
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: celery-scaledobject
spec:
  scaleTargetRef:
    name: celery-worker
  minReplicaCount: 1
  maxReplicaCount: 10
  triggers:
  - type: redis
    metadata:
      address: redis-host:6379
      listName: celery
      listLength: "5"
''',
    'tests/__init__.py': '',
    'tests/conftest.py': '''
import pytest
from django.contrib.auth import get_user_model
from apps.tenants.models import Tenant

@pytest.fixture
def tenant(db):
    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant",
        schema_name="test_schema",
        is_active=True
    )

@pytest.fixture
def other_tenant(db):
    return Tenant.objects.create(
        name="Other Tenant",
        slug="other-tenant",
        schema_name="other_schema",
        is_active=True
    )

@pytest.fixture
def user(db):
    User = get_user_model()
    return User.objects.create_user(username="testuser", password="password")
''',
    'tests/test_multitenancy.py': '''
import pytest
from apps.tenants.context import set_current_tenant
from apps.inventory.models import Item

@pytest.mark.django_db
def test_tenant_isolation(tenant, other_tenant):
    # Set context to first tenant
    set_current_tenant(tenant)
    Item.objects.create(tenant=tenant, name="Tenant 1 Item", stock=10)
    
    # Set context to second tenant
    set_current_tenant(other_tenant)
    Item.objects.create(tenant=other_tenant, name="Tenant 2 Item", stock=20)
    
    # Assert isolation
    set_current_tenant(tenant)
    items = Item.objects.all()
    assert items.count() == 1
    assert items.first().name == "Tenant 1 Item"
    
    set_current_tenant(other_tenant)
    items = Item.objects.all()
    assert items.count() == 1
    assert items.first().name == "Tenant 2 Item"
    
    # Cleanup context
    set_current_tenant(None)
    assert Item.objects.all().count() == 2
''',
    'tests/test_outbox.py': '''
import pytest
from apps.outbox.models import OutboxMessage
from apps.outbox.services import publish_event
from django.db import transaction

@pytest.mark.django_db
def test_outbox_publish_event():
    with transaction.atomic():
        publish_event("USER_CREATED", {"user_id": 1, "email": "test@example.com"})
        
    messages = OutboxMessage.objects.filter(status='PENDING')
    assert messages.count() == 1
    assert messages.first().event_type == "USER_CREATED"
''',
    'tests/test_websockets.py': '''
import pytest
import jwt
from django.conf import settings
from channels.testing import WebsocketCommunicator
from config.asgi import application
from apps.notifications.services import send_tenant_notification

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_websocket_connection_and_notification(tenant, user):
    # Generate JWT token
    token = jwt.encode({"user_id": user.id}, settings.SECRET_KEY, algorithm="HS256")
    
    # Connect
    communicator = WebsocketCommunicator(
        application, 
        f"/ws/notifications/{tenant.id}/?token={token}"
    )
    connected, subprotocol = await communicator.connect()
    assert connected
    
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()
    group_name = f"tenant_{tenant.id}_user_{user.id}"
    
    await channel_layer.group_send(
        group_name,
        {
            "type": "tenant_message",
            "message": "Hello from backend!"
        }
    )
    
    # Receive
    response = await communicator.receive_json_from()
    assert response["message"] == "Hello from backend!"
    
    await communicator.disconnect()
''',
    'tests/test_advisory_locks.py': '''
import pytest
from django.db import transaction
from apps.inventory.models import Item
from apps.inventory.services import create_reservation, create_reservation_advisory
from apps.tenants.context import set_current_tenant

@pytest.mark.django_db(transaction=True)
def test_advisory_lock_success(tenant):
    set_current_tenant(tenant)
    item = Item.objects.create(tenant=tenant, name="Laptop", stock=10)
    
    from django.db import connection
    if connection.vendor != 'postgresql':
        pytest.skip("Advisory locks only supported on PostgreSQL")
        
    reservation = create_reservation_advisory(item.id, 2, tenant)
    
    item.refresh_from_db()
    assert item.stock == 8
    assert reservation.quantity == 2
''',
}

for path, content in files.items():
    write_file(path, content)

print("Files created successfully.")
