class BuyCommand:
    def __init__(self, account_id, ticker, exchange_code, quantity, price, date):
        self.account_id = account_id
        self.ticker = ticker
        self.exchange_code = exchange_code
        self.quantity = quantity
        self.price = price
        self.date = date
