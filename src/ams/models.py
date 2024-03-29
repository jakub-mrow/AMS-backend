from django.contrib.auth.models import User
from django.db import models


class Account(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    last_transaction_date = models.DateTimeField(blank=True, null=True)
    last_save_date = models.DateTimeField(blank=True, null=True)
    xirr = models.DecimalField(max_digits=17, decimal_places=10, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s {self.name} account"

    class Meta:
        unique_together = ('name', 'user')


class AccountHistory(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    date = models.DateField()


class AccountHistoryBalance(models.Model):
    account_history = models.ForeignKey(AccountHistory, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3)


class AccountTransaction(models.Model):
    DEPOSIT = 'deposit'
    WITHDRAWAL = 'withdrawal'
    BUY = 'buy'
    SELL = 'sell'
    DIVIDEND = 'dividend'
    COST = 'cost'
    TRANSACTION_TYPE_CHOICES = (
        (DEPOSIT, 'Deposit'),
        (WITHDRAWAL, 'Withdrawal'),
        (BUY, 'Buy'),
        (SELL, 'Sell'),
        (DIVIDEND, 'dividend'),
        (COST, 'cost')
    )

    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=17, decimal_places=2)
    currency = models.CharField(max_length=10)
    date = models.DateTimeField()
    correlation_id = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.type} of {self.amount} for {self.account}"


class AccountBalance(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='balances')
    currency = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=17, decimal_places=2)

    class Meta:
        unique_together = ('account', 'currency')


class Exchange(models.Model):
    name = models.CharField(max_length=128)
    mic = models.CharField(max_length=10)
    country = models.CharField(max_length=128, null=True, blank=True)
    code = models.CharField(max_length=20)
    timezone = models.CharField(max_length=100, null=True, blank=True)
    opening_hour = models.TimeField(null=True, blank=True)
    closing_hour = models.TimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name}"


class AssetTransaction(models.Model):
    BUY = 'buy'
    SELL = 'sell'
    PRICE = 'price'
    DIVIDEND = 'dividend'
    TRANSACTION_TYPE_CHOICES = (
        (BUY, 'Buy'),
        (SELL, 'Sell'),
        (PRICE, 'Price'),
        (DIVIDEND, 'Dividend')
    )

    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='stock_transaction')
    asset_id = models.IntegerField()
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=13, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    date = models.DateTimeField()
    pay_currency = models.CharField(max_length=3, null=True, blank=True)
    exchange_rate = models.DecimalField(max_digits=13, decimal_places=2, null=True, blank=True)
    commission = models.DecimalField(max_digits=13, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.transaction_type} of {self.quantity} for {self.price} for {self.account_id}"


class Asset(models.Model):
    STOCK_TYPE_CHOICES = [
        ('STOCK', 'Stock'),
        ('CRYPTO', 'Cryptocurrency'),
    ]
    isin = models.CharField(max_length=12, null=True, blank=True)
    ticker = models.CharField(max_length=10)
    name = models.CharField(max_length=128)
    currency = models.CharField(max_length=3)
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE)
    type = models.CharField(max_length=6, choices=STOCK_TYPE_CHOICES, default='STOCK')

    def __str__(self):
        return f"{self.name} on {self.exchange}"


class AssetBalance(models.Model):
    asset_id = models.IntegerField()
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='stock_balance')
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=13, decimal_places=2)
    result = models.DecimalField(max_digits=13, decimal_places=2)
    average_price = models.DecimalField(max_digits=13, decimal_places=2)
    last_save_date = models.DateField(null=True)
    first_event_date = models.DateField(null=True)
    last_transaction_date = models.DateTimeField(null=True)

    def __str__(self):
        return f"{self.quantity} of {self.asset_id} for {self.account_id}"


class AssetBalanceHistory(models.Model):
    asset_id = models.IntegerField()
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    date = models.DateField()
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=13, decimal_places=2)
    result = models.DecimalField(max_digits=13, decimal_places=2)


class AccountPreferences(models.Model):
    account = models.OneToOneField(Account, on_delete=models.CASCADE, related_name='account_preferences', unique=True)
    base_currency = models.CharField(max_length=3)


class FavoriteAsset(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=50)
    exchange = models.CharField(max_length=50, null=True, blank=True)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=50)
    country = models.CharField(max_length=50, null=True, blank=True)
    currency = models.CharField(max_length=10)
    isin = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        unique_together = ('code', 'exchange')
