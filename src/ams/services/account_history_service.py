import decimal
from collections import defaultdict

from ams import models
from ams.services import eod_service


class AccountHistoryDto:
    def __init__(self, amount, date):
        self.amount = amount
        self.date = date


def get_account_history_dtos(account):
    histories = models.AccountHistory.objects.filter(account=account).order_by('date')
    base_currency = account.account_preferences.base_currency
    history_balances = models.AccountHistoryBalance.objects.filter(account_history__in=histories).select_related(
        'account_history')
    stock_history_balances = models.AssetBalanceHistory.objects.filter(account=account)
    stocks = models.Asset.objects.filter(id__in=stock_history_balances.values_list('asset_id', flat=True).distinct())
    asset_id_to_currency = {stock.id: stock.currency for stock in stocks}
    date_to_history = {history.date: history for history in histories}
    date_to_history_balances = defaultdict(list)
    for balance in history_balances:
        date_to_history_balances[balance.account_history.date].append(balance)
    date_to_stock_history_balances = defaultdict(list)
    for balance in stock_history_balances:
        date_to_stock_history_balances[balance.date].append(balance)

    currencies = []
    for balance in history_balances:
        if balance.currency != base_currency:
            currencies.append(f'{balance.currency}{base_currency}')
    for currency in asset_id_to_currency.values():
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
        for balance in date_to_history_balances[date]:
            if balance.currency == base_currency:
                amount += balance.amount
            else:
                amount += balance.amount * decimal.Decimal(currency_pairs[f'{balance.currency}{base_currency}'])
        if date in date_to_stock_history_balances:
            for stock_balance in date_to_stock_history_balances[date]:
                if asset_id_to_currency[stock_balance.asset_id] == base_currency:
                    amount += stock_balance.quantity * stock_balance.price
                else:
                    rate = decimal.Decimal(
                        currency_pairs[f'{asset_id_to_currency[stock_balance.asset_id]}{base_currency}'])
                    amount += stock_balance.quantity * stock_balance.price * rate
        dtos.append(AccountHistoryDto(amount, date))
    return dtos
