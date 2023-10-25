import datetime
from ams import models


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

    stock_balance.last_transaction_date = datetime.datetime.now()

    stock_balance.save()
