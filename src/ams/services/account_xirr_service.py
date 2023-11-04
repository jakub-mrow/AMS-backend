from ams.models import Transaction, StockBalance
from django.db.models.functions import TruncDate
from pyxirr import xirr
from datetime import date


def calculate_account_xirr(account):
    transactions = Transaction.objects.filter(
        account_id=account.id,
        type__in=[Transaction.DEPOSIT, Transaction.WITHDRAWAL]
    ).annotate(transaction_date=TruncDate('date'))

    dates = []
    amounts = []
    for transaction in transactions:
        dates.append(transaction.transaction_date)

        if transaction.type == Transaction.DEPOSIT:
            amounts.append(transaction.amount)
        elif transaction.type == Transaction.WITHDRAWAL:
            amounts.append(-transaction.amount)

    stock_balances = StockBalance.objects.filter(account_id=account.id)

    today = date.today()

    for stock_balance in stock_balances:
        dates.append(today)
        amounts.append(stock_balance.amount)

    transactions_tuple = zip(dates, amounts)
    current_xirr = xirr(transactions_tuple)
    account.xirr = current_xirr
    account.save()


