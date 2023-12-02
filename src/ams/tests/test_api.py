import pytest


@pytest.mark.django_db
def test_account_create(client):
    data = {'name': 'Main account'}
    response = client.post('/api/accounts', data, format='json')
    assert response.status_code == 201
    print("OK")

    response = client.get('/api/accounts')
    assert response.status_code == 200
    print("OK")

    assert len(response.data) == 1
    print("OK")
    account_id = response.data[0]['id']

    response = client.delete(f'/api/accounts/{account_id}')
    assert response.status_code == 204
    print("OK")

    response = client.get('/api/accounts')
    assert response.status_code == 200
    print("OK")

    assert len(response.data) == 0
    print("OK")
