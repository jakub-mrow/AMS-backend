import logging

from celery import shared_task

from ams.services import stock_balance_service

logger = logging.getLogger(__name__)


@shared_task
def update_stock_price_task():
    logger.info("Updating stock price")
    stock_balance_service.update_stock_price()
