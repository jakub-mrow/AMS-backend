from django.db import models
from django.contrib.auth.models import User


class Task(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, help_text="task owner")
    description = models.CharField(max_length=128, help_text="Task description")


class Account(models.Model):
    currency = models.CharField(max_length=3)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=13, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.user.username}'s {self.currency} account"

    class Meta:
        unique_together = ('currency', 'user')


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


class StockTransaction(models.Model):
    BUY = 'buy'
    SELL = 'sell'
    TRANSACTION_TYPE_CHOICES = (
        (BUY, 'Buy'),
        (SELL, 'Sell'),
    )

    account_id = models.IntegerField()   # TODO: change to foreign key
    isin = models.CharField(max_length=12)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=13, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    exchange_id = models.IntegerField()
    currency = models.CharField(max_length=3)

    def __str__(self):
        return f"{self.transaction_type} of {self.quantity} for {self.price} for {self.account_id}"

class Exchange(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=128)

    def __str__(self):
        return f"{self.name}"

class Stock(models.Model):
    isin = models.CharField(max_length=12, primary_key=True)
    name = models.CharField(max_length=128)
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.name} on {self.exchange}"
