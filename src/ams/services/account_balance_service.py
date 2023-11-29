import decimal
from datetime import timedelta, datetime

from django.db import transaction

from ams import models, tasks
from ams.services import eod_service


def add_transaction_to_account_balance(transaction, account):
    account_balance, created = models.AccountBalance.objects.get_or_create(
        account_id=transaction.account_id,
        currency=transaction.currency,
        defaults={
            'amount': 0,
        }
    )

    if (created or account.last_save_date.date() >= transaction.date.date()
            or account.last_transaction_date > transaction.date):
        rebuild_account_balance(account, transaction.date.date())
    else:
        update_account_balance(transaction, account, account_balance)
        account_balance.save()
        account.save()

    tasks.calculate_account_xirr_task.delay(account.id)


def update_account_balance(transaction, account, account_balance):
    if transaction.type == 'deposit' or transaction.type == 'sell' or transaction.type == 'dividend':
        account_balance.amount += transaction.amount
    elif transaction.type == 'withdrawal' or transaction.type == 'buy':
        account_balance.amount -= transaction.amount

    if account.last_transaction_date:
        if transaction.date > account.last_transaction_date:
            account.last_transaction_date = transaction.date
    else:
        account.last_transaction_date = transaction.date


def add_transaction_from_stock(stock_transaction, stock, account):
    if stock_transaction.transaction_type == models.StockTransaction.DIVIDEND:
        amount = stock_transaction.price
    else:
        commission = stock_transaction.commission if stock_transaction.commission else 0
        amount = stock_transaction.quantity * stock_transaction.price + commission
    currency = stock_transaction.pay_currency if stock_transaction.pay_currency else stock.currency

    account_transaction = models.Transaction.objects.create(
        account_id=stock_transaction.account_id,
        type=stock_transaction.transaction_type,
        amount=amount,
        currency=currency,
        date=stock_transaction.date,
        account=account,
        correlation_id=stock_transaction.id
    )
    account_transaction.save()
    add_transaction_to_account_balance(account_transaction, account)


def modify_transaction_from_stock(stock_transaction, stock, account):
    account_transaction = models.Transaction.objects.get(correlation_id=stock_transaction.id)
    old_account_transaction_date = account_transaction.date

    currency = stock_transaction.pay_currency if stock_transaction.pay_currency else stock.currency
    commission = stock_transaction.commission if stock_transaction.commission else 0
    amount = stock_transaction.quantity * stock_transaction.price + commission

    account_transaction.type = stock_transaction.transaction_type
    account_transaction.amount = amount
    account_transaction.currency = currency
    account_transaction.date = stock_transaction.date
    account_transaction.account = account
    account_transaction.correlation_id = stock_transaction.id

    account_transaction.save()
    older_transaction_date = min(old_account_transaction_date.date(), account_transaction.date.date())
    rebuild_account_balance(account_transaction.account, older_transaction_date)


def rebuild_account_balance(account, rebuild_date):
    account_history = models.AccountHistory.objects.filter(account_id=account.id,
                                                           date=rebuild_date - timedelta(days=1)).first()
    # TODO Put fetching account histories and account balances to function
    account_balances = models.AccountBalance.objects.filter(account_id=account.id)
    account_balances_by_currency = {account_balance.currency: account_balance for account_balance in account_balances}
    currencies = account_balances_by_currency.keys()

    if account_history:
        account_balance_histories = models.AccountHistoryBalance.objects.filter(account_history__id=account_history.id)
        account_balance_histories_by_currency = {account_balance_history.currency: account_balance_history
                                                 for account_balance_history in account_balance_histories}

        for currency in currencies:
            if currency in account_balance_histories_by_currency:
                account_balances_by_currency[currency].amount = account_balance_histories_by_currency[currency].amount
            else:
                account_balances_by_currency[currency].amount = 0
    else:
        for currency in currencies:
            account_balances_by_currency[currency].amount = 0

    current_date = rebuild_date
    yesterday = datetime.now().date() - timedelta(days=1)

    while current_date <= yesterday:
        for transaction in models.Transaction.objects.filter(date__date=current_date,
                                                             account_id=account.id).order_by('date'):
            update_account_balance(transaction, account, account_balances_by_currency[transaction.currency])

        for currency in currencies:
            account_history, success = models.AccountHistory.objects.get_or_create(account_id=account.id,
                                                                                   date=current_date,
                                                                                   defaults={
                                                                                       'account_id': account.id,
                                                                                       'date': current_date
                                                                                   })
            account_history_balance, created = models.AccountHistoryBalance.objects.get_or_create(
                account_history_id=account_history.id,
                currency=currency,
                defaults={
                    'amount': 0
                }
            )

            account_history_balance.amount = account_balances_by_currency[currency].amount
            account_history_balance.save()

        current_date += timedelta(days=1)

    for transaction in models.Transaction.objects.filter(date__date=current_date).order_by('date'):
        update_account_balance(transaction, account, account_balances_by_currency[transaction.currency])

    for account_balance in account_balances_by_currency.values():
        account_balance.save()
    account.last_save_date = yesterday
    account.save()


def modify_transaction(account_transaction, old_transaction_date):
    older_transaction_date = min(old_transaction_date.date(), account_transaction.date.date())
    rebuild_account_balance(account_transaction.account, older_transaction_date)


@transaction.atomic
def delete_transaction(account_transaction):
    account_transaction.delete()
    rebuild_account_balance(account_transaction.account, account_transaction.date.date())


def get_account_value(account):
    base_currency = account.account_preferences.base_currency
    account_balances = models.AccountBalance.objects.filter(account=account)
    stock_balances = models.StockBalance.objects.filter(account=account)
    stocks = models.Stock.objects.filter(isin__in=stock_balances.values_list('isin', flat=True).distinct())
    isin_to_currency = {stock.isin: stock.currency for stock in stocks}

    currencies = []
    for balance in account_balances:
        if balance.currency != base_currency:
            currencies.append(f'{balance.currency}{base_currency}')
    for currency in isin_to_currency.values():
        if currency != base_currency:
            currencies.append(f'{currency}{base_currency}')
    currencies = list(set(currencies))
    currency_pairs = {}
    if len(currencies) > 0:
        if len(currencies) == 1:
            currency_pairs = eod_service.get_current_currency_price(currencies[0])
        else:
            currency_pairs = eod_service.get_current_currency_prices(currencies)

    amount = 0
    for balance in account_balances:
        if balance.currency == base_currency:
            amount += balance.amount
        else:
            amount += balance.amount * decimal.Decimal(currency_pairs[f'{balance.currency}{base_currency}'])
    for stock_balance in stock_balances:
        if isin_to_currency[stock_balance.isin] == base_currency:
            amount += stock_balance.quantity * stock_balance.price
        else:
            rate = decimal.Decimal(
                currency_pairs[f'{isin_to_currency[stock_balance.isin]}{base_currency}'])
            amount += stock_balance.quantity * stock_balance.price * rate
    return amount
