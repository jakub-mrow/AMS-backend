from datetime import timedelta, date
from ams import models


def add_transaction_to_account_balance(transaction, account, account_balance):
    if transaction.type == 'deposit' or transaction.type == 'buy':
        account_balance.amount += transaction.amount
    elif transaction.type == 'withdrawal' or transaction.type == 'sell':
        account_balance.amount -= transaction.amount

    if account.last_transaction_date:
        if transaction.date > account.last_transaction_date:
            account.last_transaction_date = transaction.date
    else:
        account.last_transaction_date = transaction.date

    account_balance.save()
    account.save()


def rebuild_account_balance(account, transaction_date):
    account_history = models.AccountHistory.objects.filter(account_id=account.id,
                                                           date=transaction_date - timedelta(days=1)).first()

    account_balances = models.AccountBalance.objects.filter(account_id=account.id)
    account_balances_by_currency = {account_balance.currency: account_balance for account_balance in account_balances}
    currencies = account_balances_by_currency.keys()

    account_balance_histories = models.AccountHistoryBalance.objects.filter(account_history__id=account_history.id)
    account_balance_histories_by_currency = {account_balance_history.currency: account_balance_history
                                             for account_balance_history in account_balance_histories}

    for currency in currencies:
        if currency in account_balance_histories_by_currency:
            account_balances_by_currency[currency].amount = account_balance_histories_by_currency[currency].amount
        else:
            account_balances_by_currency[currency].amount = 0

    desired_date = date(transaction_date.year, transaction_date.month, transaction_date.day)

    transactions_on_date = models.Transaction.objects.filter(date__date=desired_date).order_by('date')

    for transaction in transactions_on_date:
        add_transaction_to_account_balance(transaction, account, account_balances_by_currency[transaction.currency])

    for balance in account_balances:
        balance.save()


def add_transaction_from_stock(stock_transaction, stock, account):
    account_transaction = models.Transaction.objects.create(
        account_id=stock_transaction.account_id,
        type=stock_transaction.transaction_type,
        amount=stock_transaction.quantity * stock_transaction.price,
        currency=stock.currency,
        date=stock_transaction.date,
        account=account,
        correlation_id=stock_transaction.id
    )
    account_transaction.save()

    account_balance = models.AccountBalance.objects.filter(account_id=stock_transaction.account_id,
                                                           currency=stock.currency).first()
    if not account_balance:
        account_balance = models.AccountBalance.objects.create(
            account_id=stock_transaction.account_id,
            currency=stock.currency,
            amount=0
        )
        account_balance.save()

    add_transaction_to_account_balance(account_transaction, account, account_balance)
