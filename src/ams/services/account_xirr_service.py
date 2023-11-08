import logging

from ams.models import Transaction, StockBalance, AccountPreferences, Stock
from ams.services.eod_service import get_current_currency_prices, get_current_currency_price
from django.db.models.functions import TruncDate
from pyxirr import xirr
from datetime import date


def calculate_account_xirr(account):
    logging.debug('CALCULATING XIRR')
    try:
        base_currency = account.account_preferences.base_currency
    except AccountPreferences.DoesNotExist:
        # Probably won't be needed when we have a default preferences object for account
        base_currency = "PLN"

    transactions = Transaction.objects.filter(
        account_id=account.id,
        type__in=[Transaction.DEPOSIT, Transaction.WITHDRAWAL]
    ).annotate(transaction_date=TruncDate('date'))
    transaction_currencies = [f'{currency}{base_currency}' for currency in transactions.values_list('currency', flat=True).distinct()]

    stock_balances = StockBalance.objects.filter(account_id=account.id)
    stock_currencies = []
    for stock_balance in stock_balances:
        stock = Stock.objects.get(isin=stock_balance.isin)
        currency_pair = f'{stock.currency}{base_currency}'
        if currency_pair not in stock_currencies:
            stock_currencies.append(currency_pair)

    currencies = list(set(transaction_currencies).symmetric_difference(set(stock_currencies)))
    if len(currencies) > 1:
        currency_pairs = get_current_currency_prices(currencies)
    else:
        currency_pairs = get_current_currency_price(currencies[0])

    dates = []
    amounts = []
    for transaction in transactions:
        currency_pair = f'{transaction.currency}{base_currency}'
        if transaction.currency == base_currency:
            currency_difference = 1.0
        else:
            currency_difference = currency_pairs[currency_pair]

        dates.append(transaction.transaction_date)

        if transaction.type == Transaction.DEPOSIT:
            transaction_amount = float(transaction.amount) * currency_difference
            amounts.append(transaction_amount)
        elif transaction.type == Transaction.WITHDRAWAL:
            transaction_amount = float(-transaction.amount) * currency_difference
            amounts.append(transaction_amount)

    today = date.today()

    for stock_balance in stock_balances:
        stock = Stock.objects.get(isin=stock_balance.isin)
        currency_pair = f'{stock.currency}{base_currency}'

        if stock.currency == base_currency:
            currency_difference = 1
        else:
            currency_difference = currency_pairs[currency_pair]
        print(currency_difference)
        balance_amount = float(stock_balance.value) * currency_difference

        dates.append(today)
        amounts.append(balance_amount)

    transactions_tuple = zip(dates, amounts)
    current_xirr = xirr(transactions_tuple)
    account.xirr = current_xirr

    account.save()
