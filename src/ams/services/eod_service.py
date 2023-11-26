import logging
from datetime import datetime

import requests

from main.settings import EOD_TOKEN, EOD_API_URL

logger = logging.getLogger(__name__)


def get_current_price(stock, date):
    params = {
        'api_token': EOD_TOKEN,
        'fmt': 'json',
        'from': date.strftime('%Y-%m-%d'),
        'to': date.strftime('%Y-%m-%d')

    }
    url = f'{EOD_API_URL}/eod/{stock.ticker}.{stock.exchange.code}'

    try:
        response = requests.get(url, timeout=10.0, params=params)
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
        response = requests.get(url, timeout=10.0, params=params)
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


def search(query):
    params = {
        'api_token': EOD_TOKEN,
        'fmt': 'json'
    }
    url = f'{EOD_API_URL}/search/{query}'
    response = requests.get(url, timeout=30.0, params=params)
    data = response.json()
    return data


CURRENCY_PRICE_CACHE = dict()


def get_current_currency_price(currency_pair):
    global CURRENCY_PRICE_CACHE
    now = datetime.now().date()
    if currency_pair in CURRENCY_PRICE_CACHE and now == CURRENCY_PRICE_CACHE[currency_pair]['time']:
        return {currency_pair: CURRENCY_PRICE_CACHE[currency_pair]['close']}

    params = {
        'api_token': EOD_TOKEN,
        'fmt': 'json'
    }
    url = f'{EOD_API_URL}/real-time/{currency_pair}.FOREX'

    try:
        response = requests.get(url, timeout=30.0, params=params)
        data = response.json()
        if data['close'] == 'NA':
            logger.exception('No data for currencies pair')
            return None
        else:
            current_price = data['close']
            CURRENCY_PRICE_CACHE[currency_pair] = {'close': current_price, 'time': now}

        return {currency_pair: current_price}

    except Exception as e:
        logger.exception(e)
        return None


def get_current_currency_prices(pairs):
    global CURRENCY_PRICE_CACHE
    result = dict()
    now = datetime.now().date()
    pairs_copy = pairs.copy()
    for pair in pairs_copy:
        if pair in CURRENCY_PRICE_CACHE and now == CURRENCY_PRICE_CACHE[pair]['time']:
            result[pair] = CURRENCY_PRICE_CACHE[pair]['close']
            pairs.remove(pair)
    if len(pairs) == 1:
        result[pairs[0]] = get_current_currency_price(pairs[0])[pairs[0]]
        return result
    elif len(pairs) == 0:
        return result

    params = {
        'api_token': EOD_TOKEN,
        'fmt': 'json',
        's': ".FOREX,".join(pairs[1:]) + ".FOREX"
    }
    url = f'{EOD_API_URL}/real-time/{pairs[0]}.FOREX'

    try:
        response = requests.get(url, timeout=30.0, params=params)
        data = response.json()
        for item in data:
            if item['close'] == 'NA':
                logging.exception('No data for currencies pair')
                return None
            else:
                current_price = item['close']
                CURRENCY_PRICE_CACHE[item['code'].split(".")[0]] = {'close': current_price, 'time': now}

            result[item['code'].split(".")[0]] = current_price
        return result

    except Exception as e:
        logger.exception(e)
        return None


def get_price_changes(stock, begin, end):
    params = {
        'api_token': EOD_TOKEN,
        'fmt': 'json',
        'from': begin.strftime('%Y-%m-%d'),
        'to': end.strftime('%Y-%m-%d')

    }
    url = f'{EOD_API_URL}/eod/{stock.ticker}.{stock.exchange.code}'

    try:
        response = requests.get(url, timeout=10.0, params=params)
        data = response.json()
        return data
    except Exception as e:
        logger.exception(e)
        return []
