from _decimal import Decimal

from rest_framework import serializers
from rest_framework.fields import CurrentUserDefault
from ams import models


class TaskSerializer(serializers.ModelSerializer):
    description = serializers.CharField(help_text="description")

    class Meta:
        model = models.Task
        fields = ("id", "description",)


class AccountCreateSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=CurrentUserDefault())

    class Meta:
        model = models.Account
        fields = ('id', 'currency', 'user')


class AccountSerializer(serializers.ModelSerializer):
    balance = serializers.DecimalField(max_digits=13, decimal_places=2, coerce_to_string=False)

    class Meta:
        model = models.Account
        fields = ('id', 'currency', 'balance')


class DepositSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=13, decimal_places=2)


class WithdrawalSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=13, decimal_places=2)


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Transaction
        fields = ('id', 'account', 'transaction_type', 'amount', 'date')


class ExchangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Exchange
        fields = ('id', 'name')
