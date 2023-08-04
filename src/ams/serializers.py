from ams import models
from rest_framework import serializers
from rest_framework.fields import CurrentUserDefault


class AccountCreateSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=CurrentUserDefault())

    class Meta:
        model = models.Account
        fields = ('id', 'name', 'user')


class AccountSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id')

    class Meta:
        model = models.Account
        fields = ('id', 'name', 'user_id')


class DepositSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=13, decimal_places=2)


class WithdrawalSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=13, decimal_places=2)


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Transaction
        fields = ('id', 'account', 'transaction_type', 'amount', 'date')
