from abc import abstractmethod, ABC

import pandas as pd
from pandas.core.dtypes.common import is_integer_dtype, is_numeric_dtype

from ams import models
from ams.services import eod_service


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
        result['type'] = "BUY"
        result.loc[result.iloc[:, self.LOCAL_VALUE] > 0, 'type'] = "SELL"
        result['quantity'] = result.iloc[:, self.QUANTITY]
        result['price'] = result.iloc[:, self.PRICE]
        result['pay_currency'] = result.iloc[:, self.CURRENCY]
        result['exchange_rate'] = result.iloc[:, self.EXCHANGE_RATE]
        result['commission'] = result.iloc[:, self.COMMISSION]
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
        return models.Stock.objects.filter(isin=stock).prefetch_related('exchange').first()


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
        result['type'] = "BUY"
        result.loc[result.iloc[:, self.ACTION] == "Market sell", 'type'] = "SELL"
        result['quantity'] = result.iloc[:, self.NO_OF_SHARES]
        result['price'] = result.iloc[:, self.PRICE_PER_SHARE]
        result['pay_currency'] = result.iloc[:, self.CURRENCY]
        result['exchange_rate'] = 1 / result.iloc[:, self.EXCHANGE_RATE]
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
        return models.Stock.objects.filter(isin=stock).prefetch_related('exchange').first()


def get_strategy(broker, file):
    if broker == "degiro":
        return DegiroImportStockTransactionsStrategy(file)
    elif broker == "trading212":
        return Trading212ImportStockTransactionsStrategy(file)
    return None
