from django.db import models
from django.contrib.auth.models import User


class Account(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.user.username}'s {self.name} account"

    class Meta:
        unique_together = ('name', 'user')


class Transaction(models.Model):
    DEPOSIT = 'deposit'
    WITHDRAWAL = 'withdrawal'
    TRANSACTION_TYPE_CHOICES = (
        (DEPOSIT, 'Deposit'),
        (WITHDRAWAL, 'Withdrawal'),
    )

    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=13, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} of {self.amount} for {self.account}"

class Exchange(models.Model):
    name = models.CharField(max_length=128)

    def __str__(self):
        return f"{self.name}"

class StockTransaction(models.Model):
    BUY = 'buy'
    SELL = 'sell'
    TRANSACTION_TYPE_CHOICES = (
        (BUY, 'Buy'),
        (SELL, 'Sell'),
    )

    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name= 'stock_transaction')
    isin = models.CharField(max_length=12)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=13, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE)
    currency = models.CharField(max_length=3)
    date = models.DateTimeField()

    def __str__(self):
        return f"{self.transaction_type} of {self.quantity} for {self.price} for {self.account_id}"



class Stock(models.Model):
    isin = models.CharField(max_length=12, primary_key=True)
    name = models.CharField(max_length=128)
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.name} on {self.exchange}"
