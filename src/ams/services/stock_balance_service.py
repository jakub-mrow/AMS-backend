import datetime

import pytz
from pytz import timezone

from ams import models
from ams.services import eod_service


def update_stock_balance(stock_transaction, account):
    stock_balance, created = models.StockBalance.objects.get_or_create(
        isin=stock_transaction.isin,
        account=account,
        defaults={
            'last_transaction_date': datetime.datetime.now(),
            'quantity': 0,
            'result': 0,
            'value': 0,
        }
    )

    if stock_transaction.transaction_type == 'buy':
        stock_balance.quantity += stock_transaction.quantity
        stock_balance.value += stock_transaction.quantity * stock_transaction.price
    elif stock_transaction.transaction_type == 'sell':
        if stock_balance.quantity < stock_transaction.quantity:
            raise Exception('Not enough stocks to sell.')
        stock_balance.quantity -= stock_transaction.quantity
        stock_balance.value -= stock_transaction.quantity * stock_transaction.price
    elif stock_transaction.transaction_type == 'price':
        stock_balance.value = stock_transaction.price * stock_balance.quantity

    stock_balance.last_transaction_date = datetime.datetime.now()

    stock_balance.save()


def update_stock_price(utc_now=datetime.datetime.utcnow()):
    utc_now_tz = utc_now.replace(minute=0, second=0, microsecond=0).astimezone(pytz.UTC)
    window_start = utc_now_tz - datetime.timedelta(hours=5)
    window_end = utc_now_tz - datetime.timedelta(hours=4)
    weekday = window_start.weekday()
    if weekday == 5 or weekday == 6:
        return
    exchanges = models.Exchange.objects.all()
    for exchange in exchanges:
        tz = timezone(exchange.timezone)
        closing_time = window_start.replace(
            hour=exchange.closing_hour.hour,
            minute=exchange.closing_hour.minute,
            second=exchange.closing_hour.second,
            microsecond=exchange.closing_hour.microsecond,
            tzinfo=None
        )
        utc_closing_time = tz.localize(closing_time).astimezone(pytz.UTC)
        if not (window_start <= utc_closing_time < window_end):
            continue
        stocks = models.Stock.objects.filter(exchange=exchange)
        for stock in stocks:
            current_price = eod_service.get_current_price(stock, utc_closing_time)
            if not current_price:
                continue
            stock_balances = models.StockBalance.objects.filter(isin=stock.isin)
            for stock_balance in stock_balances:
                stock_transaction = models.StockTransaction.objects.create(
                    isin=stock_balance.isin,
                    account=stock_balance.account,
                    transaction_type='price',
                    quantity=stock_balance.quantity,
                    price=current_price,
                    date=utc_closing_time,
                )
                stock_transaction.save()
                update_stock_balance(stock_transaction, stock_balance.account)
