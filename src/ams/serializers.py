from rest_framework import serializers
from rest_framework.fields import CurrentUserDefault

import ams.services.models
from ams import models
from ams.services import account_balance_service


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
        fields = ('id', 'name', 'user', 'last_transaction_date')


class AccountPreferencesSerializer(serializers.ModelSerializer):
    account_id = serializers.IntegerField(source='account.id', read_only=True)

    class Meta:
        model = models.AccountPreferences
        fields = ('account_id', 'base_currency', 'tax_currency')

    def create(self, validated_data):
        account_id = self.context.get('account_id')
        validated_data['account_id'] = account_id
        return super().create(validated_data)


class AccountSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id')
    balances = AccountBalanceSerializer(many=True)
    xirr = serializers.DecimalField(max_digits=17, decimal_places=10, coerce_to_string=False)
    preferences = AccountPreferencesSerializer(source='account_preferences', read_only=True)

    class Meta:
        model = models.Account
        fields = ('id', 'name', 'user_id', 'balances', 'last_transaction_date', 'last_save_date', 'xirr', 'preferences')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['value'] = account_balance_service.get_account_value(instance)
        return data


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


class ExchangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Exchange
        fields = ('id', 'name', 'mic', 'country', 'code', 'timezone', 'opening_hour', 'closing_hour')


class StockSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Stock
        fields = ('id', 'isin', 'type', 'ticker', 'name', 'exchange', 'currency')


class StockTransactionSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(max_digits=17, decimal_places=2, coerce_to_string=False)
    account_id = serializers.IntegerField(source='account.id', read_only=True)
    pay_currency = serializers.CharField(max_length=3, required=False, allow_null=True)
    exchange_rate = serializers.DecimalField(max_digits=13, decimal_places=2, required=False, allow_null=True)
    commission = serializers.DecimalField(max_digits=17, decimal_places=2, required=False, allow_null=True)

    class Meta:
        model = models.StockTransaction
        fields = (
            'id', 'asset_id', 'quantity', 'price', 'transaction_type', 'date', 'account_id', 'pay_currency',
            'exchange_rate',
            'commission')

    def create(self, validated_data):
        account_id = self.context.get('account_id')
        validated_data['account_id'] = account_id
        return super().create(validated_data)


class StockBalanceDtoSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(max_digits=13, decimal_places=2, coerce_to_string=False)
    result = serializers.DecimalField(max_digits=13, decimal_places=2, coerce_to_string=False)

    class Meta:
        model = models.StockBalance
        fields = ('asset_id', 'quantity', 'price', 'result')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        stock = models.Stock.objects.get(id=instance.asset_id)
        data['name'] = stock.name
        data['ticker'] = stock.ticker
        data['currency'] = stock.currency
        data['exchange_code'] = stock.exchange.code
        return data


class StockBalanceHistoryDtoSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(max_digits=13, decimal_places=2, coerce_to_string=False)
    result = serializers.DecimalField(max_digits=13, decimal_places=2, coerce_to_string=False)

    class Meta:
        model = models.StockBalanceHistory
        fields = ('asset_id', 'date', 'quantity', 'price', 'result')


class BuyCommandSerializer(serializers.Serializer):
    ticker = serializers.CharField(max_length=5)
    exchange_code = serializers.CharField(max_length=5)
    quantity = serializers.IntegerField()
    price = serializers.DecimalField(max_digits=13, decimal_places=2)
    date = serializers.DateTimeField()
    pay_currency = serializers.CharField(max_length=3, required=False, allow_null=True)
    exchange_rate = serializers.DecimalField(max_digits=13, decimal_places=2, required=False, allow_null=True)
    commission = serializers.DecimalField(max_digits=17, decimal_places=2, required=False, allow_null=True)

    def create(self, validated_data):
        account_id = self.context.get('account_id')
        date = validated_data.pop('date')
        return ams.services.models.BuyCommand(account_id, date=date, **validated_data)


class AccountHistoryDtoSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=13, decimal_places=2, coerce_to_string=False)
    date = serializers.DateField()


class FavoriteAssetSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.pop('user')
        return data

    class Meta:
        model = models.FavoriteAsset
        fields = '__all__'


class FileUploadSerializer(serializers.Serializer):
    file = serializers.FileField()