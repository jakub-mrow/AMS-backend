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
