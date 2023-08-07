from ams import models
from rest_framework import serializers
from rest_framework.fields import CurrentUserDefault


class AccountBalanceSerializer(serializers.ModelSerializer):
    account_id = serializers.IntegerField(source='account.id', read_only=True)
    amount = serializers.DecimalField(max_digits=17, decimal_places=2, coerce_to_string=False)

    class Meta:
        model = models.AccountBalance
        fields = ('account_id', 'currency', 'amount')


class AccountCreateSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=CurrentUserDefault())

    class Meta:
        model = models.Account
        fields = ('id', 'name', 'user')


class AccountSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id')
    balances = AccountBalanceSerializer(many=True)

    class Meta:
        model = models.Account
        fields = ('id', 'name', 'user_id', 'balances')


class TransactionCreateSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=17, decimal_places=2)
    account = serializers.IntegerField(source='account.id', read_only=True)

    class Meta:
        model = models.Transaction
        fields = ('id', 'account', 'type', 'amount', 'currency', 'date')
        read_only_fields = ('id', 'account')

    def create(self, validated_data):
        account_id = self.context.get('account_id')
        validated_data['account_id'] = account_id
        return super().create(validated_data)


class TransactionSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=17, decimal_places=2, coerce_to_string=False)
    account_id = serializers.IntegerField(source='account.id', read_only=True)

    class Meta:
        model = models.Transaction
        fields = ('id', 'account_id', 'type', 'amount', 'currency', 'date')
