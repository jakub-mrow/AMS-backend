import datetime

import pytz
from django.db import transaction
from pytz import timezone

from ams import models
from ams.services import eod_service, account_balance_service


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


def update_stock_price():
    exchanges = models.Exchange.objects.all()
    for exchange in exchanges:
        tz = timezone(exchange.timezone)
        closing_time = datetime.datetime.now().replace(
            hour=exchange.closing_hour.hour,
            minute=exchange.closing_hour.minute,
            second=exchange.closing_hour.second,
            microsecond=exchange.closing_hour.microsecond
        )
        utc_closing_time = tz.localize(closing_time).astimezone(pytz.UTC)
        utc_now = datetime.datetime.utcnow()
        utc_now = utc_now.replace(minute=0, second=0, microsecond=0)
        utc_now = utc_now.astimezone(pytz.UTC)
        if datetime.timedelta(hours=4) > utc_now - utc_closing_time or utc_now - utc_closing_time >= datetime.timedelta(
                hours=5):
            continue
        stocks = models.Stock.objects.filter(exchange=exchange)
        for stock in stocks:
            current_price = eod_service.get_current_price(stock, utc_now)
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
                    date=utc_now,
                )
                stock_transaction.save()
                update_stock_balance(stock_transaction, stock_balance.account)


@transaction.atomic
def buy_stocks(buy_command):
    try:
        account = models.Account.objects.get(id=buy_command.account_id)
    except models.Account.DoesNotExist:
        raise Exception('Account does not exist.')
    try:
        exchange = models.Exchange.objects.get(code=buy_command.exchange_code)
    except models.Exchange.DoesNotExist:
        raise Exception('Exchange does not exist.')
    try:
        stock = models.Stock.objects.get(ticker=buy_command.ticker, exchange=exchange)
    except models.Stock.DoesNotExist:
        search_result = eod_service.search(buy_command.ticker + '.' + buy_command.exchange_code)
        if len(search_result) == 0:
            raise Exception('Stock does not exist.')
        stock_from_api = search_result[0]
        stock = models.Stock.objects.create(
            isin=stock_from_api['ISIN'],
            ticker=buy_command.ticker,
            name=stock_from_api['Name'],
            currency=stock_from_api['Currency'],
            exchange=exchange
        )
    stock_transaction = models.StockTransaction(
        account=account,
        isin=stock.isin,
        quantity=buy_command.quantity,
        price=buy_command.price,
        transaction_type='buy',
        date=buy_command.date
    )

    stock_transaction.save()
    update_stock_balance(stock_transaction, account)
    account_balance_service.add_transaction_from_stock(stock_transaction, stock, account)
