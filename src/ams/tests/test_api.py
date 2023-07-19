import pytest


@pytest.mark.django_db
def test_task_create(client):
    data = {"description": "test description"}
    response = client.post('/api/tasks', data=data)
    assert response.status_code == 201

    response = client.get('/api/tasks')

    assert response.status_code == 200

    assert len(response.data) == 1
