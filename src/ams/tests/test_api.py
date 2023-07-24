import pytest


@pytest.mark.django_db
def test_task_create(client):
    data = {"description": "test description"}
    response = client.post('/api/tasks', data=data)
    assert response.status_code == 201

    response = client.get('/api/tasks')

    assert response.status_code == 200

    assert len(response.data) == 1


@pytest.mark.django_db
def test_account_create(client):
    data = {'currency': 'USD'}
    response = client.post('/api/accounts', data, format='json')
    assert response.status_code == 201

    response = client.get('/api/accounts')
    assert response.status_code == 200

    assert len(response.data) == 1
    account_id = response.data[0]['id']

    response = client.delete(f'/api/accounts/{account_id}')
    assert response.status_code == 204

    response = client.get('/api/accounts')
    assert response.status_code == 200

    assert len(response.data) == 0

