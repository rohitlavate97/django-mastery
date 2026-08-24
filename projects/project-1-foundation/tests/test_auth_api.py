import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_register_user(api_client):
    url = reverse('register')
    data = {'email': 'new@example.com', 'password': 'password123'}
    response = api_client.post(url, data)
    assert response.status_code == 201
    assert 'email' in response.data

@pytest.mark.django_db
def test_login_user(api_client, user):
    url = reverse('login')
    data = {'email': 'test@example.com', 'password': 'password123'}
    response = api_client.post(url, data)
    assert response.status_code == 200
    assert 'access' in response.data
