import logging

import pytest

logger = logging.getLogger(__name__)

@pytest.mark.django_db
def test_account_create(client):
    logger.info('start')
    data = {'name': 'Main account'}
    response = client.post('/api/accounts', data, format='json')
    assert response.status_code == 201
    logger.info('ok')

    response = client.get('/api/accounts')
    assert response.status_code == 200
    logger.info('ok')

    assert len(response.data) == 1
    logger.info('ok')
    account_id = response.data[0]['id']

    response = client.delete(f'/api/accounts/{account_id}')
    assert response.status_code == 204
    logger.info('ok')

    response = client.get('/api/accounts')
    assert response.status_code == 200
    logger.info('ok')

    assert len(response.data) == 0
    logger.info('ok')
