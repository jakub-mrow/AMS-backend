import datetime

import pytz
from pytz import timezone

from ams import models
from ams.services import eod_service


def add_stock_transaction_to_balance(stock_transaction, account):
    stock_balance, created = models.StockBalance.objects.get_or_create(
        isin=stock_transaction.isin,
        account=account,
        defaults={
            'quantity': 0,
            'result': 0,
            'value': 0,
        }
    )
    if created:
        rebuild_stock_balance(stock_balance, stock_transaction.date.date())
    else:
        if stock_balance.last_save_date >= stock_transaction.date.date():
            rebuild_stock_balance(stock_balance, stock_transaction.date.date())
        if stock_balance.last_transaction_date > stock_transaction.date:
            rebuild_stock_balance(stock_balance, datetime.datetime.now().date())
        else:
            update_stock_balance(stock_transaction, stock_balance)
            stock_balance.save()


def update_stock_balance(stock_transaction, stock_balance):
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

    if not stock_balance.last_transaction_date or stock_balance.last_transaction_date < stock_transaction.date:
        stock_balance.last_transaction_date = stock_transaction.date


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


def rebuild_stock_balance(stock_balance, rebuild_date):
    history_date = rebuild_date - datetime.timedelta(days=1)
    stock_balance_history = models.StockBalanceHistory.objects.filter(isin=stock_balance.isin,
                                                                      account=stock_balance.account,
                                                                      date=history_date).first()
    models.StockBalanceHistory.objects.filter(isin=stock_balance.isin,
                                              account=stock_balance.account,
                                              date__gte=rebuild_date).delete()

    if stock_balance_history:
        stock_balance.quantity = stock_balance_history.quantity
        stock_balance.value = stock_balance_history.value
        stock_balance.result = stock_balance_history.result
    else:
        stock_balance.quantity = 0
        stock_balance.value = 0
        stock_balance.result = 0

    transactions_on_date = models.StockTransaction.objects.filter(date__gte=rebuild_date).order_by('date')
    today = datetime.datetime.now().date()
    yesterday = today - datetime.timedelta(days=1)
    for day in range((yesterday - rebuild_date).days + 1):
        for transaction in transactions_on_date.filter(date__date=rebuild_date + datetime.timedelta(days=day)):
            update_stock_balance(transaction, stock_balance)

        models.StockBalanceHistory.objects.create(
            isin=stock_balance.isin,
            account=stock_balance.account,
            date=rebuild_date + datetime.timedelta(days=day),
            quantity=stock_balance.quantity,
            value=stock_balance.value,
            result=stock_balance.result,
        )

    today_transactions = models.StockTransaction.objects.filter(date__date=today).order_by('date')

    for transaction in today_transactions:
        update_stock_balance(transaction, stock_balance)
    stock_balance.last_save_date = yesterday
    stock_balance.save()
