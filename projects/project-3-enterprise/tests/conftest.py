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
