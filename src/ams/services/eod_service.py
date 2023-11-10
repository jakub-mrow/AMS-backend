import logging

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
        response = requests.get(url, timeout=30.0, params=params)
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


def get_current_currency_price(currency_pair):
    params = {
        'api_token': EOD_TOKEN,
        'fmt': 'json'
    }
    url = f'{EOD_API_URL}/real-time/{currency_pair}.FOREX'

    try:
        response = requests.get(url, timeout=30.0, params=params)
        data = response.json()
        print(data)
        if data['close'] == 'NA':
            logger.exception('No data for currencies pair')
            return None
        else:
            current_price = data['close']

        return {currency_pair: current_price}

    except Exception as e:
        logger.exception(e)
        return None


def get_current_currency_prices(pairs):
    params = {
        'api_token': EOD_TOKEN,
        'fmt': 'json',
        's': ".FOREX,".join(pairs[1:]) + ".FOREX"
    }
    url = f'{EOD_API_URL}/real-time/{pairs[0]}.FOREX'

    result = dict()
    try:
        response = requests.get(url, timeout=30.0, params=params)
        data = response.json()
        print(data)
        for item in data:
            if item['close'] == 'NA':
                logging.exception('No data for currencies pair')
                return None
            else:
                current_price = item['close']

            result[item['code'].split(".")[0]] = current_price
        return result

    except Exception as e:
        logger.exception(e)
        return None
