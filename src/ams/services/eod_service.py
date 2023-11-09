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


def get_bulk_last_day_price(stocks, exchange, date):
    params = {
        'api_token': EOD_TOKEN,
        'fmt': 'json',
        'date': date.strftime('%Y-%m-%d'),
        'symbols': ','.join([f"{stock.ticker}.{exchange.code}" for stock in stocks])
    }
    url = f'{EOD_API_URL}/eod-bulk-last-day/{exchange.code}'
    try:
        response = requests.get(url, timeout=30.0, params=params)
        data = response.json()
        if len(data) == 0:
            logger.warning(
                'No data for stocks from ' + exchange.code + ' on date: ' + date.strftime(
                    "%Y-%m-%d"))
            return {}
        return {d['code']: d['close'] for d in data}
    except Exception as e:
        logger.exception(e)
        return {}
