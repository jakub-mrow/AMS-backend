from datetime import datetime, timedelta

from ams import models


def save_account_history():
    date = datetime.now().date()
    history_date = date - timedelta(days=1)

    # Get all accounts
    accounts = models.Account.objects.all()

    for account in accounts:

        account_history = models.AccountHistory.objects.create(account=account, date=history_date)
        account_balances = models.AccountBalance.objects.filter(account=account).all()

        for balance in account_balances:
            models.AccountHistoryBalance.objects.create(
                account_history=account_history,
                amount=balance.amount,
                currency=balance.currency
            )

        account.last_save_date = history_date
        account.save()
