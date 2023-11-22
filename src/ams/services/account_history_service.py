from ams import models


class AccountHistoryDto:
    def __init__(self, amount, date):
        self.amount = amount
        self.date = date


def get_account_history_dtos(account):
    histories = models.AccountHistory.objects.filter(account=account).order_by('date')
    dtos = []
    for history in histories:
        amount = 0
        for balance in models.AccountHistoryBalance.objects.filter(account_history=history):
            amount += balance.amount
        dtos.append(AccountHistoryDto(amount, history.date))
    return dtos
