import decimal

from ams import models
from ams.services import eod_service


class AccountHistoryDto:
    def __init__(self, amount, date):
        self.amount = amount
        self.date = date


def get_account_history_dtos(account):
    histories = models.AccountHistory.objects.filter(account=account).order_by('date')
    base_currency = account.account_preferences.base_currency
    history_balances = models.AccountHistoryBalance.objects.filter(account_history__in=histories)
    stock_history_balances = models.StockBalanceHistory.objects.filter(account=account)
    stocks = models.Stock.objects.filter(isin__in=stock_history_balances.values_list('isin', flat=True).distinct())
    isin_to_currency = {stock.isin: stock.currency for stock in stocks}
    date_to_history = {history.date: history for history in histories}

    currencies = []
    for balance in history_balances:
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

    dtos = []
    for date in date_to_history.keys():
        amount = 0
        for balance in history_balances.filter(account_history=date_to_history[date]):
            if balance.currency == base_currency:
                amount += balance.amount
            else:
                amount += balance.amount * decimal.Decimal(currency_pairs[f'{balance.currency}{base_currency}'])
        for stock_balance in stock_history_balances.filter(account=account, date=date):
            if isin_to_currency[stock_balance.isin] == base_currency:
                amount += stock_balance.result
            else:
                amount += stock_balance.result * decimal.Decimal(
                    currency_pairs[f'{isin_to_currency[stock_balance.isin]}{base_currency}'])
        dtos.append(AccountHistoryDto(amount, date))
    return dtos
