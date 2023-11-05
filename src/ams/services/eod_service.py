import logging

import requests

from main.settings import EOD_TOKEN, EOD_API_URL

logger = logging.getLogger(__name__)


def get_current_price(stock, date):
    url = f'{EOD_API_URL}/eod/{stock.ticker}.{stock.exchange.code}?api_token={EOD_TOKEN}&fmt=json&from={date.strftime("%Y-%m-%d")}&to={date.strftime("%Y-%m-%d")}'

    try:
        response = requests.get(url, timeout=30.0)
        data = response.json()
        if len(data) == 0:
            logger.warning(
                'No data for stock: ' + stock.ticker + '.' + stock.exchange.code + ' on date: ' + date.strftime(
                    "%Y-%m-%d"))
            return None
        return data[0]['close']
    except Exception as e:
        logger.exception(e)
        return None
