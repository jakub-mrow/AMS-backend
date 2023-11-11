import logging

from celery import shared_task
from ams.models import Account
from ams.services import stock_balance_service, account_xirr_service

logger = logging.getLogger(__name__)


@shared_task
def add(x, y):
    return x + y


@shared_task
def update_stock_price_task():
    logger.info("Updating stock price")
    stock_balance_service.update_stock_price()


@shared_task
def calculate_account_xirr_task(account_id):
    account = Account.objects.get(pk=account_id)
    logger.info("Calculating account xirr")
    account_xirr_service.calculate_account_xirr(account)
