import csv
from abc import abstractmethod, ABC

import numpy as np
import pandas as pd
from django.db import transaction
from pandas.core.dtypes.common import is_integer_dtype, is_numeric_dtype

from ams import models
from ams.services import eod_service, stock_balance_service, account_balance_service, account_xirr_service
from ams.services.stock_balance_service import NotEnoughStockException


class IncorrectFileFormatException(Exception):
    pass


class UnknownAssetException(Exception):
    pass


class ImportStockTransactionsStrategy(ABC):
    REQUIRED_COLUMNS = ["ticker", "exchange", "date", "type", "quantity", "price", "pay_currency", "exchange_rate",
                        "commission"]

    def __init__(self, data):
        self.data = data

    def convert(self):
        if not self.is_valid(self.data):
            raise IncorrectFileFormatException()
        data = self.convert_rows(self.data)
        data = self.remove_columns(data)
        return data

    def remove_columns(self, data):
        for column in data.columns:
            if column not in self.REQUIRED_COLUMNS:
                data.drop(column, axis=1, inplace=True)
        return data

    def find_stocks(self, stocks):
        result = dict()
        for stock in stocks:
            search = self.find_stock(stock)
            if search:
                result[stock] = (search.ticker, search.exchange.code)
            else:
                search = eod_service.search(stock)
                if len(search) > 0:
                    result[stock] = (search[0]['Code'], search[0]['Exchange'])
                else:
                    raise UnknownAssetException("Unknown asset: " + stock)
        return result

    @abstractmethod
    def convert_rows(self, data):
        pass

    @abstractmethod
    def is_valid(self, data):
        pass

    @abstractmethod
    def find_stock(self, stock):
        pass


class DegiroImportStockTransactionsStrategy(ImportStockTransactionsStrategy):
    DATE = 0
    TIME = 1
    ISIN = 3
    QUANTITY = 6
    PRICE = 7
    LOCAL_VALUE = 9
    CURRENCY = 12
    EXCHANGE_RATE = 13
    COMMISSION = 14

    def __init__(self, file):
        super().__init__(pd.read_csv(file))

    def convert_rows(self, data):
        result = data.copy()
        isin_to_ticker = self.find_stocks(result.iloc[:, self.ISIN].unique())
        result['ticker'] = result.iloc[:, self.ISIN].map(isin_to_ticker).apply(lambda x: x[0])
        result['exchange'] = result.iloc[:, self.ISIN].map(isin_to_ticker).apply(lambda x: x[1])
        result['date'] = pd.to_datetime(result.iloc[:, self.DATE] + " " + result.iloc[:, self.TIME],
                                        format="%d-%m-%Y %H:%M")
        result['type'] = "buy"
        result.loc[result.iloc[:, self.LOCAL_VALUE] > 0, 'type'] = "sell"
        result['quantity'] = result.iloc[:, self.QUANTITY]
        result['price'] = result.iloc[:, self.PRICE]
        result['pay_currency'] = result.iloc[:, self.CURRENCY]
        result['exchange_rate'] = result.iloc[:, self.EXCHANGE_RATE]
        result['commission'] = result.iloc[:, self.COMMISSION].abs()
        return result

    def is_valid(self, data):
        if len(data.columns) < 15:
            return False
        if not data.iloc[:, self.DATE].str.match(r"^\d{2}-\d{2}-\d{4}$").all():
            return False
        if not data.iloc[:, self.TIME].str.match(r"^\d{2}:\d{2}$").all():
            return False
        if not is_integer_dtype(data.iloc[:, self.QUANTITY]):
            return False
        if not is_numeric_dtype(data.iloc[:, self.PRICE]):
            return False
        if not is_numeric_dtype(data.iloc[:, self.LOCAL_VALUE]):
            return False
        if not is_numeric_dtype(data.iloc[:, self.EXCHANGE_RATE]):
            return False
        if not is_numeric_dtype(data.iloc[:, self.COMMISSION]):
            return False
        return True

    def find_stock(self, stock):
        return models.Asset.objects.filter(isin=stock).prefetch_related('exchange').first()


class Trading212ImportStockTransactionsStrategy(ImportStockTransactionsStrategy):
    ACTION = 0
    TIME = 1
    ISIN = 2
    NO_OF_SHARES = 5
    PRICE_PER_SHARE = 6
    CURRENCY = 7
    EXCHANGE_RATE = 8

    def __init__(self, file):
        super().__init__(pd.read_csv(file))

    def convert_rows(self, data):
        result = data.copy()
        isin_to_ticker = self.find_stocks(result.iloc[:, self.ISIN].unique())
        result['ticker'] = result.iloc[:, self.ISIN].map(isin_to_ticker).apply(lambda x: x[0])
        result['exchange'] = result.iloc[:, self.ISIN].map(isin_to_ticker).apply(lambda x: x[1])
        result['date'] = pd.to_datetime(result.iloc[:, self.TIME], format="%Y-%m-%d %H:%M:%S")
        result['type'] = "buy"
        result.loc[result.iloc[:, self.ACTION] == "Market sell", 'type'] = "sell"
        result['quantity'] = result.iloc[:, self.NO_OF_SHARES]
        result['price'] = result.iloc[:, self.PRICE_PER_SHARE]
        result['pay_currency'] = result.apply(lambda x: x[self.CURRENCY] if x[self.EXCHANGE_RATE] != 1 else None,
                                              axis=1)
        result['exchange_rate'] = result.apply(lambda x: 1/x[self.EXCHANGE_RATE] if x[self.EXCHANGE_RATE] != 1 else None,
                                               axis=1)
        result['commission'] = None
        return result

    def is_valid(self, data):
        if len(data.columns) < 9:
            return False
        actions = data.iloc[:, self.ACTION].unique()
        if not set(actions).issubset({"Market buy", "Market sell"}):
            return False
        if not data.iloc[:, self.TIME].str.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$").all():
            return False
        if not is_integer_dtype(data.iloc[:, self.NO_OF_SHARES]):
            return False
        if not is_numeric_dtype(data.iloc[:, self.PRICE_PER_SHARE]):
            return False
        if not is_numeric_dtype(data.iloc[:, self.EXCHANGE_RATE]):
            return False
        return True

    def find_stock(self, stock):
        return models.Asset.objects.filter(isin=stock).prefetch_related('exchange').first()


class ExanteImportStockTransactionsStrategy(ImportStockTransactionsStrategy):
    ISIN = 3
    OPERATION = 4
    DATE = 5
    SUM = 6
    ASSETS = 7

    def __init__(self, file):
        super().__init__(pd.read_csv(file, sep="\t", quoting=csv.QUOTE_ALL, quotechar='"'))

    def convert_rows(self, data):
        isins = data.iloc[:, self.ISIN].unique()
        isins = [isin for isin in isins if str(isin) != "nan"]
        isin_to_ticker = self.find_stocks(isins)
        grouped = data.groupby(data.iloc[:, self.DATE])
        results = []
        for i, group in grouped:
            results.append({
                'ticker': isin_to_ticker[group.iloc[0, self.ISIN]][0],
                'exchange': isin_to_ticker[group.iloc[0, self.ISIN]][1],
                'date': pd.to_datetime(group.iloc[0, self.DATE], format="%Y-%m-%d %H:%M:%S"),
                'type': "buy" if group.iloc[0, self.SUM] > 0 else "sell",
                'quantity': int(abs(group.iloc[0, self.SUM])),
                'price': round(abs(group.iloc[1, self.SUM] / group.iloc[0, self.SUM]), 2),
                'pay_currency': None,
                'exchange_rate': None,
                'commission': abs(group.iloc[2, self.SUM])
            })
        return pd.DataFrame(results)

    def is_valid(self, data):
        if len(data.columns) < 8:
            return False
        operations = data.iloc[:, self.OPERATION].unique()
        if not set(operations).issubset({"TRADE", "COMMISSION"}):
            return False
        if not data.iloc[:, self.DATE].str.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$").all():
            return False
        grouped = data.groupby(np.arange(len(data)) // 3)
        for i, group in grouped:
            if group.iloc[0, self.OPERATION] != "TRADE" or group.iloc[1, self.OPERATION] != "TRADE" or group.iloc[2,
            self.OPERATION] != "COMMISSION":
                return False
            if not group.iloc[0, self.SUM].is_integer():
                return False
            if not is_numeric_dtype(group.iloc[1, self.SUM]) or not is_numeric_dtype(group.iloc[2, self.SUM]):
                return False
        return True

    def find_stock(self, stock):
        return models.Asset.objects.filter(isin=stock).prefetch_related('exchange').first()


class DmBosImportStockTransactionsStrategy(ImportStockTransactionsStrategy):
    DATE = 0
    ASSET = 1
    QUANTITY = 2
    OPERATION = 3
    PRICE = 4
    COMMISSION = 6
    CURRENCY = 8
    EXCHANGE_RATE = 9

    def __init__(self, file):
        super().__init__(pd.read_csv(file, encoding_errors="ignore", sep=";", decimal=","))

    def convert_rows(self, data):
        result = data.copy()
        name_to_ticker = self.find_stocks(result.iloc[:, self.ASSET].unique())
        result['ticker'] = result.iloc[:, self.ASSET].map(name_to_ticker).apply(lambda x: x[0])
        result['exchange'] = result.iloc[:, self.ASSET].map(name_to_ticker).apply(lambda x: x[1])
        result['date'] = pd.to_datetime(result.iloc[:, self.DATE], format="%Y-%m-%d") + pd.Timedelta(hours=12)
        result['type'] = "buy"
        result.loc[result.iloc[:, self.OPERATION] == "S", 'type'] = "sell"
        result['quantity'] = result.iloc[:, self.QUANTITY]
        result['price'] = result.iloc[:, self.PRICE] / result.iloc[:, self.EXCHANGE_RATE]
        result['pay_currency'] = result.iloc[:, self.CURRENCY]
        result['exchange_rate'] = result.iloc[:, self.EXCHANGE_RATE]
        result['commission'] = result.iloc[:, self.COMMISSION]
        return result

    def is_valid(self, data):
        if len(data.columns) < 10:
            return False
        if not data.iloc[:, self.DATE].str.match(r"^\d{4}-\d{2}-\d{2}$").all():
            return False
        if not is_integer_dtype(data.iloc[:, self.QUANTITY]):
            return False
        operations = data.iloc[:, self.OPERATION].unique()
        if not set(operations).issubset({"K", "S"}):
            return False
        if not is_numeric_dtype(data.iloc[:, self.PRICE]):
            return False
        if not is_numeric_dtype(data.iloc[:, self.EXCHANGE_RATE]):
            return False
        if not is_numeric_dtype(data.iloc[:, self.COMMISSION]):
            return False
        return True

    def find_stock(self, stock):
        return models.Asset.objects.filter(isin=stock).prefetch_related('exchange').first()


def get_strategy(broker, file):
    if broker == "degiro":
        return DegiroImportStockTransactionsStrategy(file)
    elif broker == "trading212":
        return Trading212ImportStockTransactionsStrategy(file)
    elif broker == "exante":
        return ExanteImportStockTransactionsStrategy(file)
    elif broker == "dmbos":
        return DmBosImportStockTransactionsStrategy(file)
    return None


def import_csv(file, account):
    names = ["ticker", "exchange", "date", "type", "quantity", "price", "pay_currency", "exchange_rate", "commission"]
    transactions = pd.read_csv(file, names=names)
    if len(transactions.columns) < 9:
        raise IncorrectFileFormatException()
    if not transactions.iloc[:, 2].str.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$").all():
        raise IncorrectFileFormatException()
    if not is_integer_dtype(transactions.iloc[:, 4]):
        raise IncorrectFileFormatException()
    operations = transactions.iloc[:, 3].apply(lambda x: x.lower()).unique()
    if not set(operations).issubset({"buy", "sell"}):
        raise IncorrectFileFormatException()
    if not is_numeric_dtype(transactions.iloc[:, 5]):
        raise IncorrectFileFormatException()
    if not is_numeric_dtype(transactions.iloc[:, 8]):
        raise IncorrectFileFormatException()
    transactions['date'] = pd.to_datetime(transactions['date'], format="%Y-%m-%d %H:%M:%S")
    transactions['ticker_exchange'] = transactions['ticker'] + transactions['exchange']
    ticker_unique = transactions['ticker_exchange'].unique()
    stock_transactions_list = []
    for ticker in ticker_unique:
        current = transactions[transactions['ticker_exchange'] == ticker]
        stock_transactions_list.append(current)

    account_rebuild_date = None
    for stock_transactions in stock_transactions_list:
        try:
            exchange = models.Exchange.objects.get(code=stock_transactions.iloc[0]["exchange"])
        except models.Exchange.DoesNotExist:
            raise Exception('Exchange does not exist.')
        try:
            stock = models.Asset.objects.get(ticker=stock_transactions.iloc[0]["ticker"],
                                             exchange=exchange)
        except models.Asset.DoesNotExist:
            search_result = eod_service.search(
                stock_transactions.iloc[0]["ticker"] + '.' + stock_transactions.iloc[0]["exchange"])
            if len(search_result) == 0:
                raise Exception('Stock does not exist.')
            stock_from_api = search_result[0]
            stock = models.Asset.objects.create(
                isin=stock_from_api['ISIN'],
                ticker=stock_transactions.iloc[0]["ticker"],
                name=stock_from_api['Name'],
                currency=stock_from_api['Currency'],
                exchange=exchange,
                type="STOCK"
            )
        try:
            with transaction.atomic():
                stock_transactions_to_save = []
                for index, stock_transaction in stock_transactions.iterrows():
                    pay_currency = stock_transaction["pay_currency"] if not pd.isna(
                        stock_transaction["pay_currency"]) else None
                    exchange_rate = stock_transaction["exchange_rate"] if not pd.isna(
                        stock_transaction["exchange_rate"]) else None
                    commission = stock_transaction["commission"] if not pd.isna(
                        stock_transaction["commission"]) else None
                    db_stock_transaction = models.AssetTransaction(
                        account=account,
                        asset_id=stock.id,
                        quantity=stock_transaction["quantity"],
                        price=stock_transaction["price"],
                        transaction_type=stock_transaction["type"].lower(),
                        date=stock_transaction["date"],
                        pay_currency=pay_currency,
                        exchange_rate=exchange_rate,
                        commission=commission
                    )
                    stock_transactions_to_save.append(db_stock_transaction)
                db_stock_transactions = models.AssetTransaction.objects.bulk_create(stock_transactions_to_save)
                account_transactions_to_save = []
                for db_stock_transaction in db_stock_transactions:
                    account_transactions_to_save.append(
                        account_balance_service.add_transaction_from_stock_for_import(db_stock_transaction, stock, account)
                    )
                models.AccountTransaction.objects.bulk_create(account_transactions_to_save)
                stock_balance, created = models.AssetBalance.objects.get_or_create(
                    asset_id=stock.id,
                    account=account,
                    defaults={
                        'quantity': 0,
                        'result': 0,
                        'price': 0,
                        'average_price': 0,
                    }
                )
                first_date = stock_transactions["date"].min()
                account_rebuild_date = min(account_rebuild_date, first_date.date()) if account_rebuild_date else first_date.date()
                if created:
                    stock_balance_service.fetch_missing_price_changes(stock_balance, stock, first_date.date())
                else:
                    if not stock_balance.first_event_date or stock_balance.first_event_date >= first_date.date():
                        stock_balance_service.fetch_missing_price_changes(stock_balance, stock, first_date.date())
                    else:
                        stock_balance_service.rebuild_stock_balance(stock_balance, first_date.date())
                account_balance, created = models.AccountBalance.objects.get_or_create(
                    account_id=account.id,
                    currency=stock_transactions.iloc[0]["pay_currency"] if not pd.isna(stock_transactions.iloc[0][
                        "pay_currency"]) else stock.currency,
                    defaults={
                        'amount': 0,
                    }
                )
        except NotEnoughStockException:
            pass
    account_balance_service.rebuild_account_balance(account, account_rebuild_date)
    account_xirr_service.calculate_account_xirr(account)
