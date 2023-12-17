import concurrent
import logging
from datetime import datetime, timedelta

import pandas as pd
import requests
from dateutil.relativedelta import relativedelta

from ams import models
from main.settings import EOD_TOKEN, EOD_API_URL

logger = logging.getLogger(__name__)


def get_current_price(stock, exchange):
    params = {
        'api_token': EOD_TOKEN,
        'fmt': 'json'
    }
    url = f'{EOD_API_URL}/real-time/{stock}.{exchange}'

    try:
        response = requests.get(url, timeout=10.0, params=params)
        data = response.json()
        if data['previousClose'] == 'NA':
            logger.warning('No data for stock: ' + stock + '.' + exchange)
            return None
        return data
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
        while len(data) == 0:
            date -= timedelta(days=1)
            params['date'] = date.strftime('%Y-%m-%d')
            response = requests.get(url, timeout=10.0, params=params)
            data = response.json()
        return {d['code']: d['adjusted_close'] for d in data}
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
        while len(data) == 0 or data[0]['date'] != begin.strftime('%Y-%m-%d'):
            begin -= timedelta(days=1)
            params['from'] = begin.strftime('%Y-%m-%d')
            response = requests.get(url, timeout=10.0, params=params)
            data = response.json()
        return data
    except Exception as e:
        logger.exception(e)
        return []


def get_price_changes_2(stock, exchange, begin, end, period):
    params = {
        'api_token': EOD_TOKEN,
        'fmt': 'json',
        'period': period
    }
    if begin:
        params['from'] = begin.strftime('%Y-%m-%d')
    if end:
        params['to'] = end.strftime('%Y-%m-%d')

    url = f'{EOD_API_URL}/eod/{stock}.{exchange}'

    try:
        response = requests.get(url, timeout=10.0, params=params)
        data = response.json()
        return data
    except Exception as e:
        logger.exception(e)
        return []


def get_stock_details(stock, exchange, period, from_date, to_date):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        price_changes_future = executor.submit(get_price_changes_2, stock, exchange, from_date, to_date, period)
        current_price_future = executor.submit(get_current_price, stock, exchange)

    price_changes = price_changes_future.result()
    current_info = current_price_future.result()
    exchange_info = models.Exchange.objects.filter(code=exchange).first()
    percentage_change = ((current_info['close'] - current_info['previousClose']) / current_info['previousClose']) * 100
    stock_details = {
        'price_changes': price_changes,
        'exchange_info': exchange_info,
        'current_price': current_info['close'],
        'previous_close': current_info['previousClose'],
        'percentage_change_previous_close': round(percentage_change, 2)
    }

    return stock_details


def get_stock_history(stock, exchange, from_date, to_date):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        price_changes_future = executor.submit(get_price_changes_2, stock, exchange, from_date, to_date, 'd')
        current_price_future = executor.submit(get_current_price, stock, exchange)

    eod_data = price_changes_future.result()
    current_info = current_price_future.result()

    df = pd.DataFrame(eod_data)
    df["date"] = pd.to_datetime(df["date"])
    oldest_date = df["date"].min()
    newest_date = df["date"].max()
    date_range = pd.date_range(start=oldest_date, end=newest_date)
    merged_df = pd.merge(df, pd.DataFrame(date_range, columns=["date"]), on="date", how="right")
    merged_df = merged_df.sort_values(by="date")

    merged_df["close"].fillna(method='ffill', inplace=True)
    merged_df["adjusted_close"].fillna(method='ffill', inplace=True)
    merged_df["high"].fillna(method='ffill', inplace=True)
    current_date = datetime.now()

    current_price = current_info['close']
    time_deltas = [
        relativedelta(days=7),
        relativedelta(months=1),
        relativedelta(months=3),
        relativedelta(months=6),
        relativedelta(years=1),
        relativedelta(years=3),
        relativedelta(years=5),
    ]

    percentage_changes = {}

    for delta in time_deltas:
        start_date = current_date - delta
        on_day = merged_df[merged_df['date'] == start_date.strftime('%Y-%m-%d')]
        start_price = on_day.iloc[0]['adjusted_close']
        percentage_change = round(((current_price - start_price) / start_price) * 100, 2)
        percentage_changes[delta] = percentage_change

    all_time = merged_df.iloc[0]['adjusted_close']
    all_time = round(((current_price - all_time) / all_time) * 100, 2)

    yesterday = current_info['previousClose']
    today = round((current_info['close'] - yesterday) / yesterday * 100, 2)

    stock_history = {
        'today': today,
        'week': percentage_changes[time_deltas[0]],
        'month': percentage_changes[time_deltas[1]],
        'three_months': percentage_changes[time_deltas[2]],
        'six_months': percentage_changes[time_deltas[3]],
        'year': percentage_changes[time_deltas[4]],
        'three_years': percentage_changes[time_deltas[5]],
        'five_years': percentage_changes[time_deltas[6]],
        'all_time': all_time
    }

    return stock_history


def get_stock_news(stock):
    params = {
        'api_token': EOD_TOKEN,
        'fmt': 'json',
        'limit': 50,
        's': stock
    }
    url = f'{EOD_API_URL}/news'

    try:
        response = requests.get(url, timeout=10.0, params=params)
        data = response.json()
        news_list = []
        for item in data:
            utc_time = datetime.fromisoformat(item['date']).strftime("%Y-%m-%dT%H:%M:%SZ")
            if "yahoo" in item['link'].split("/")[2]:
                news_list.append({
                    'title': item['title'].replace('\n', ''),
                    'link': item['link'],
                    'date': utc_time
                })
            if len(news_list) == 10:
                break

        return news_list
    except Exception as e:
        logger.exception(e)
        return []
