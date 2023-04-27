import pytest

from django.contrib.auth.models import User

from rest_framework.test import APIClient


@pytest.fixture
def client():
    client = APIClient()
    username = 'unknown'
    password = 'unknown123123'
    email = 'unknown@email.com'
    
    register_data = {'username': username, 'password': password, 'email': email}
    client.post('/auth/register/', data=register_data)

    login_data = {'username': username, 'password': password}
    response = client.post("/auth/login/", data=login_data)

    token = response.json().get('access', "")
    client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)

    return client
