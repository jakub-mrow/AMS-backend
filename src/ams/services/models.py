class BuyCommand:
    def __init__(self, account_id, ticker, exchange_code, quantity, price, date, pay_currency, exchange_rate,
                 commission):
        self.account_id = account_id
        self.ticker = ticker
        self.exchange_code = exchange_code
        self.quantity = quantity
        self.price = price
        self.date = date
        self.pay_currency = pay_currency
        self.exchange_rate = exchange_rate
        self.commission = commission
