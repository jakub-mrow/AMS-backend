from abc import abstractmethod, ABC


class ImportStockTransactionsStrategy(ABC):
    @abstractmethod
    def convert(self, file):
        pass

    @abstractmethod
    def is_valid(self, file):
        pass


class DegiroImportStockTransactionsStrategy(ImportStockTransactionsStrategy):
    def convert(self, file):
        return file

    def is_valid(self, file):
        return True


def get_strategy(broker):
    if broker == "degiro":
        return DegiroImportStockTransactionsStrategy()
    return None