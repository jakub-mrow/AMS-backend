import datetime
import decimal
from collections import defaultdict

import pytz
from django.db import transaction
from pytz import timezone

from ams import models
from ams.services import eod_service, account_balance_service


class NotEnoughStockException(Exception):
    pass


def add_stock_transaction_to_balance(stock_transaction, stock, account):
    stock_balance, created = models.StockBalance.objects.get_or_create(
        asset_id=stock_transaction.asset_id,
        account=account,
        defaults={
            'quantity': 0,
            'result': 0,
            'price': 0,
            'average_price': 0
        }
    )
    if created:
        fetch_missing_price_changes(stock_balance, stock, stock_transaction.date.date())
    else:
        if not stock_balance.first_event_date or stock_balance.first_event_date > stock_transaction.date.date():
            fetch_missing_price_changes(stock_balance, stock, stock_transaction.date.date())
        elif stock_balance.last_save_date >= stock_transaction.date.date():
            rebuild_stock_balance(stock_balance, stock_transaction.date.date())
        elif stock_balance.last_transaction_date > stock_transaction.date:
            rebuild_stock_balance(stock_balance, datetime.datetime.now().date())
        else:
            update_stock_balance(stock_transaction, stock_balance)
            if stock_transaction.transaction_type == models.StockTransaction.BUY or \
                    stock_transaction.transaction_type == models.StockTransaction.SELL:
                update_average_price(stock_balance)
            update_current_result(stock_balance)
            stock_balance.save()
    return stock_balance


def update_stock_balance(stock_transaction, stock_balance):
    if stock_transaction.transaction_type == 'buy':
        stock_balance.quantity += stock_transaction.quantity
    elif stock_transaction.transaction_type == 'sell':
        if stock_balance.quantity < stock_transaction.quantity:
            raise NotEnoughStockException
        stock_balance.quantity -= stock_transaction.quantity
    elif stock_transaction.transaction_type == 'price':
        stock_balance.price = stock_transaction.price
    elif stock_transaction.transaction_type == 'dividend':
        pass

    if not stock_balance.last_transaction_date or stock_balance.last_transaction_date < stock_transaction.date:
        stock_balance.last_transaction_date = stock_transaction.date


def update_average_price(stock_balance):
    stock_transactions = list(models.StockTransaction.objects.filter(
        asset_id=stock_balance.asset_id,
        account=stock_balance.account
    ).order_by('date'))
    stock_history = list()
    for transaction in stock_transactions:
        if transaction.transaction_type == 'buy':
            stock_history.append((transaction.quantity, transaction.price))
        elif transaction.transaction_type == 'sell':
            remaining_quantity = transaction.quantity
            for i, history in enumerate(stock_history):
                if remaining_quantity <= 0:
                    break

                if history[0] >= remaining_quantity:
                    new_quantity = history[0] - remaining_quantity
                    stock_history[i] = (new_quantity, history[1])
                    break
                else:
                    remaining_quantity -= history[0]
                    stock_history[i] = (0, history[1])
    stock_history = list([history for history in stock_history if history[0] > 0])
    if len(stock_history) == 0:
        stock_balance.average_price = 0
        return
    average_price = 0
    for history in stock_history:
        average_price += history[0] * history[1]
    average_price /= stock_balance.quantity
    stock_balance.average_price = average_price


def update_current_result(stock_balance):
    stock_balance.result = (stock_balance.price - stock_balance.average_price) / stock_balance.average_price


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
        if len(stocks) == 0:
            continue
        current_prices = eod_service.get_bulk_last_day_price(stocks, exchange, utc_closing_time)
        for stock in stocks:
            if stock.ticker not in current_prices:
                continue
            current_price = current_prices[stock.ticker]
            stock_balances = models.StockBalance.objects.filter(asset_id=stock.id)
            for stock_balance in stock_balances:
                stock_transaction = models.StockTransaction.objects.create(
                    asset_id=stock_balance.asset_id,
                    account=stock_balance.account,
                    transaction_type='price',
                    quantity=0,
                    price=current_price,
                    date=utc_closing_time.replace(hour=0, minute=0, second=0, microsecond=0,
                                                  tzinfo=None) + datetime.timedelta(days=1)
                )
                stock_transaction.save()
                add_stock_transaction_to_balance(stock_transaction, stock, stock_balance.account)


def fetch_missing_price_changes(stock_balance, stock, begin):
    end = stock_balance.first_event_date if stock_balance.first_event_date else datetime.datetime.now().date()
    begin = begin - datetime.timedelta(days=1)
    end = end - datetime.timedelta(days=1)
    if begin > end:
        begin = end
    price_changes = eod_service.get_price_changes(stock, begin, end)

    first_event_date = begin
    to_save = []
    for price_change in price_changes:
        date = datetime.datetime.strptime(price_change['date'], '%Y-%m-%d') + datetime.timedelta(days=1)
        to_save.append(models.StockTransaction(
            asset_id=stock_balance.asset_id,
            account=stock_balance.account,
            transaction_type='price',
            quantity=0,
            price=price_change['adjusted_close'],
            date=date,
        ))
        first_event_date = min(first_event_date, date.date())
    models.StockTransaction.objects.bulk_create(to_save)
    stock_balance.first_event_date = first_event_date
    rebuild_stock_balance(stock_balance, first_event_date)


def rebuild_stock_balance(stock_balance, rebuild_date):
    history_date = rebuild_date - datetime.timedelta(days=1)
    stock_balance_history = models.StockBalanceHistory.objects.filter(asset_id=stock_balance.asset_id,
                                                                      account=stock_balance.account,
                                                                      date=history_date).first()
    models.StockBalanceHistory.objects.filter(asset_id=stock_balance.asset_id,
                                              account=stock_balance.account,
                                              date__gte=rebuild_date).delete()

    if stock_balance_history:
        stock_balance.quantity = stock_balance_history.quantity
        stock_balance.price = stock_balance_history.price
        stock_balance.result = stock_balance_history.result
    else:
        stock_balance.quantity = 0
        stock_balance.price = 0
        stock_balance.result = 0

    today = datetime.datetime.now().date()
    yesterday = today - datetime.timedelta(days=1)
    stock_transactions = models.StockTransaction.objects.filter(asset_id=stock_balance.asset_id,
                                                                  account=stock_balance.account,
                                                                  date__range=[rebuild_date, yesterday]).order_by('date')
    stock_transactions_by_date = defaultdict(list)
    for stock_transaction in stock_transactions:
        stock_transactions_by_date[stock_transaction.date.date()].append(stock_transaction)

    to_save = []
    for day in range((yesterday - rebuild_date).days + 1):
        for stock_transaction in stock_transactions_by_date[rebuild_date + datetime.timedelta(days=day)]:
            update_stock_balance(stock_transaction, stock_balance)

        to_save.append(models.StockBalanceHistory(
            asset_id=stock_balance.asset_id,
            account=stock_balance.account,
            date=rebuild_date + datetime.timedelta(days=day),
            quantity=stock_balance.quantity,
            price=stock_balance.price,
            result=stock_balance.result,
        ))
    models.StockBalanceHistory.objects.bulk_create(to_save)

    today_transactions = models.StockTransaction.objects.filter(date__date=today).order_by('date')

    for stock_transaction in today_transactions:
        update_stock_balance(stock_transaction, stock_balance)
    stock_balance.last_save_date = yesterday
    update_average_price(stock_balance)
    update_current_result(stock_balance)
    stock_balance.save()


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
            exchange=exchange,
            type="STOCK" if buy_command.exchange_code != "CC" else "CRYPTO"
        )
    stock_transaction = models.StockTransaction(
        account=account,
        asset_id=stock.id,
        quantity=buy_command.quantity,
        price=buy_command.price,
        transaction_type='buy',
        date=buy_command.date,
        pay_currency=buy_command.pay_currency,
        exchange_rate=buy_command.exchange_rate,
        commission=buy_command.commission
    )

    stock_transaction.save()
    add_stock_transaction_to_balance(stock_transaction, stock, account)
    account_balance_service.add_transaction_from_stock(stock_transaction, stock, account)


def modify_stock_transaction(stock_transaction, old_stock_transaction_date):
    stock_balance = models.StockBalance.objects.get(asset_id=stock_transaction.asset_id,
                                                    account=stock_transaction.account)
    stock = models.Stock.objects.get(id=stock_transaction.asset_id)
    older_transaction_date = min(old_stock_transaction_date.date(), stock_transaction.date.date())
    if stock_balance.first_event_date > older_transaction_date:
        fetch_missing_price_changes(stock_balance, stock, older_transaction_date)
    else:
        rebuild_stock_balance(stock_balance, older_transaction_date)

    if models.Transaction.objects.filter(correlation_id=stock_transaction.id).exists():
        account_balance_service.modify_transaction_from_stock(stock_transaction, stock, stock_transaction.account)


@transaction.atomic
def delete_stock_transaction(stock_transaction):
    stock_balance = models.StockBalance.objects.get(asset_id=stock_transaction.asset_id,
                                                    account=stock_transaction.account)
    stock_transaction_id = stock_transaction.id
    stock_transaction.delete()
    rebuild_stock_balance(stock_balance, stock_transaction.date.date())

    if models.Transaction.objects.filter(correlation_id=stock_transaction_id).exists():
        account_transaction = models.Transaction.objects.get(correlation_id=stock_transaction_id)
        account_balance_service.delete_transaction(account_transaction)


def get_stock_price_in_base_currency(stock_balance, stock):
    stock_currency = stock.currency
    base_currency = stock_balance.account.account_preferences.base_currency
    if stock_currency == base_currency:
        return stock_balance.price, stock_currency
    currency_pair = f'{stock_currency}{base_currency}'
    rates = eod_service.get_current_currency_price(currency_pair)
    value_in_base = stock_balance.price * decimal.Decimal(rates[currency_pair])
    return value_in_base.quantize(decimal.Decimal('0.01')), base_currency
