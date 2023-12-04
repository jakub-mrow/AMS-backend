import logging
from datetime import date

from django.db.models.functions import TruncDate
from pyxirr import xirr

from ams.models import Transaction, StockBalance, AccountPreferences, Stock, AccountBalance
from ams.services.eod_service import get_current_currency_prices, get_current_currency_price


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
    transaction_currencies = [f'{currency}{base_currency}' for currency in
                              transactions.values_list('currency', flat=True).distinct() if currency != base_currency]

    stock_balances = StockBalance.objects.filter(account_id=account.id)
    stock_currencies = []

    for stock_balance in stock_balances:
        stock = Stock.objects.get(id=stock_balance.asset_id)
        if stock.currency == base_currency:
            continue
        currency_pair = f'{stock.currency}{base_currency}'
        if currency_pair not in stock_currencies:
            stock_currencies.append(currency_pair)

    currencies = list(set(transaction_currencies + stock_currencies))

    if len(currencies) > 0:
        if len(currencies) == 1:
            currency_pairs = get_current_currency_price(currencies[0])
        else:
            currency_pairs = get_current_currency_prices(currencies)
    else:
        currency_pairs = {f"{base_currency}{base_currency}": 1.0}

    if currency_pairs:
        currency_pairs[f"{base_currency}{base_currency}"] = 1.0
        dates = []
        amounts = []
        for transaction in transactions:
            currency_pair = f'{transaction.currency}{base_currency}'
            currency_difference = currency_pairs[currency_pair]

            dates.append(transaction.transaction_date)

            if transaction.type == Transaction.DEPOSIT:
                transaction_amount = float(-transaction.amount) * currency_difference
                amounts.append(transaction_amount)
            elif transaction.type == Transaction.WITHDRAWAL:
                transaction_amount = float(transaction.amount) * currency_difference
                amounts.append(transaction_amount)

        today = date.today()

        balance_sum = 0
        for stock_balance in stock_balances:
            stock = Stock.objects.get(id=stock_balance.asset_id)
            currency_pair = f'{stock.currency}{base_currency}'
            currency_difference = currency_pairs[currency_pair]

            balance_amount = float(stock_balance.price) * stock_balance.quantity * currency_difference
            balance_sum += balance_amount

        account_balances = AccountBalance.objects.filter(account_id=account.id)
        for balance in account_balances:
            currency_pair = f'{balance.currency}{base_currency}'
            currency_difference = currency_pairs[currency_pair]

            balance_amount = float(balance.amount) * currency_difference
            balance_sum += balance_amount

        dates.append(today)
        amounts.append(round(balance_sum, 2))

        transactions_tuple = zip(dates, amounts)
        current_xirr = xirr(transactions_tuple)
        account.xirr = current_xirr

        account.save()
