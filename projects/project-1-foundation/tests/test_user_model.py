import pytest
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.mark.django_db
def test_create_user():
    user = User.objects.create_user(email='test@example.com', password='pwd')
    assert user.email == 'test@example.com'
    assert user.check_password('pwd')

@pytest.mark.django_db
def test_create_superuser():
    user = User.objects.create_superuser(email='admin@example.com', password='pwd')
    assert user.is_staff
    assert user.is_superuser
