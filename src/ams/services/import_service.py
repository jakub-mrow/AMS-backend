from abc import abstractmethod, ABC
import pandas as pd


class ImportStockTransactionsStrategy(ABC):
    @abstractmethod
    def convert(self):
        pass

    @abstractmethod
    def is_valid(self):
        pass


class DegiroImportStockTransactionsStrategy(ImportStockTransactionsStrategy):
    def __init__(self, file):
        self.data = pd.read_csv(file)

    def convert(self):
        return self.data

    def is_valid(self):
        required_columns = ['Data', 'Czas', 'ISIN', 'Liczba', 'Kurs', 'Unnamed: 12', 'Kurs wymian', 'Opłata transakcyjna']
        for col in required_columns:
            if col not in self.data.columns:
                return False
        return True


def get_strategy(broker, file):
    if broker == "degiro":
        return DegiroImportStockTransactionsStrategy(file)
    return None