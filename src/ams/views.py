import logging
from datetime import timedelta, date
import os


import requests
from ams import models, serializers
from django.http import JsonResponse
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsObjectOwner
from .serializers import ExchangeSerializer

logger = logging.getLogger(__name__)
logging.getLogger("urllib3").setLevel(logging.WARNING)
EOD_TOKEN = os.getenv('EOD_TOKEN')


def add_transaction_to_account_balance(transaction, account, account_balance):
    if transaction.type == 'deposit':
        account_balance.amount += transaction.amount
    elif transaction.type == 'withdrawal':
        account_balance.amount -= transaction.amount

    if account.last_transaction_date:
        if transaction.date > account.last_transaction_date:
            account.last_transaction_date = transaction.date
    else:
        account.last_transaction_date = transaction.date

    account_balance.save()
    account.save()


def rebuild_account_balance(account, transaction_date):
    account_history = models.AccountHistory.objects.filter(account_id=account.id,
                                                           date=transaction_date - timedelta(days=1)).first()

    account_balances = models.AccountBalance.objects.filter(account_id=account.id)
    account_balances_by_currency = {account_balance.currency: account_balance for account_balance in account_balances}
    currencies = account_balances_by_currency.keys()

    account_balance_histories = models.AccountHistoryBalance.objects.filter(account_history__id=account_history.id)
    account_balance_histories_by_currency = {account_balance_history.currency: account_balance_history
                                             for account_balance_history in account_balance_histories}

    for currency in currencies:
        if currency in account_balance_histories_by_currency:
            account_balances_by_currency[currency].amount = account_balance_histories_by_currency[currency].amount
        else:
            account_balances_by_currency[currency].amount = 0

    desired_date = date(transaction_date.year, transaction_date.month, transaction_date.day)

    transactions_on_date = models.Transaction.objects.filter(date__date=desired_date).order_by('date')

    for transaction in transactions_on_date:
        add_transaction_to_account_balance(transaction, account, account_balances_by_currency[transaction.currency])

    for balance in account_balances:
        balance.save()


class AccountViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.AccountCreateSerializer
    permission_classes = (IsAuthenticated, IsObjectOwner)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logging.info("Account created")
        return Response({"msg": "Account created"}, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        account = self.get_object()
        serializer = self.get_serializer(account, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logging.info("Account updated")
        return Response({"msg": "Account updated"}, status=status.HTTP_200_OK)

    def get_queryset(self):
        return models.Account.objects.filter(user=self.request.user).order_by('id')

    def get_serializer_class(self):
        if self.request.method in ['POST', 'PUT']:
            return serializers.AccountCreateSerializer
        return serializers.AccountSerializer


class TransactionViewSet(viewsets.ViewSet):
    serializer_class = serializers.TransactionSerializer
    permission_classes = (IsAuthenticated, IsObjectOwner)

    def create(self, request, account_id):
        try:
            account = models.Account.objects.get(pk=account_id, user=self.request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found or does not belong to the user"},
                            status=status.HTTP_404_NOT_FOUND)

        serializer = serializers.TransactionCreateSerializer(data=request.data, context={'account_id': account.id})
        serializer.is_valid(raise_exception=True)
        transaction = serializer.save()
        try:
            account_balance = models.AccountBalance.objects.get(
                account_id=transaction.account_id,
                currency=transaction.currency
            )

        except models.AccountBalance.DoesNotExist:
            new_account_balance = models.AccountBalance(
                account_id=transaction.account_id,
                currency=transaction.currency,
                amount=0.00
            )
            new_account_balance.save()

            account_balance = models.AccountBalance.objects.get(
                account_id=transaction.account_id,
                currency=transaction.currency
            )

        if account.last_save_date and account.last_transaction_date:
            if account.last_transaction_date > transaction.date > account.last_save_date:
                rebuild_account_balance(account, transaction.date)
            else:
                add_transaction_to_account_balance(transaction, account, account_balance)
        else:
            add_transaction_to_account_balance(transaction, account, account_balance)

        return Response({"msg": "Transaction created."}, status=status.HTTP_201_CREATED)

    def list(self, request, account_id):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)

        transactions = models.Transaction.objects.filter(account=account).order_by('-date')

        transaction_type = self.request.query_params.get('transaction_type')
        if transaction_type in [models.Transaction.DEPOSIT, models.Transaction.WITHDRAWAL]:
            transactions = transactions.filter(transaction_type=transaction_type)
        serializer = serializers.TransactionSerializer(transactions, many=True)

        return Response(serializer.data)

    def destroy(self, request, account_id, pk=None):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)

        transaction = get_object_or_404(models.Transaction, pk=pk, account=account)
        account_balance = models.AccountBalance.objects.get(
            account_id=transaction.account_id,
            currency=transaction.currency
        )

        if transaction.type == "deposit":
            account_balance.amount -= transaction.amount
        elif transaction.type == "withdrawal":
            account_balance.amount += transaction.amount

        account_balance.save()
        transaction.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class ExchangeViewSet(viewsets.ViewSet):
    permission_classes = (IsAuthenticated,)

    def create(self, request):
        serializer = ExchangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logging.info("Exchange added")
        return Response({"msg": "Exchange added"}, status=status.HTTP_201_CREATED)

    def list(self, request):
        qs = models.Exchange.objects.all()
        serializer = serializers.ExchangeSerializer(qs, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


class StockViewSet(viewsets.ViewSet):
    permission_classes = (IsAuthenticated, IsObjectOwner)

    def create(self, request):
        try:
            exchange = models.Exchange.objects.get(pk=request.data.get("exchange"))
        except models.Exchange.DoesNotExist:
            return Response({"error": "Exchange not found."}, status=404)

        serializer = serializers.StockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(exchange=exchange)
        logging.info("Stock added")
        return Response({"msg": "Stock added"}, status=status.HTTP_201_CREATED)

    def list(self, request, exchange_id=None):
        try:
            stocks = models.Stock.objects.filter(exchange=exchange_id)
        except models.Stock.DoesNotExist:
            return Response({"error": "Stock not found."}, status=404)

        serializer = serializers.StockSerializer(stocks, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


class StockTransactionViewSet(viewsets.ViewSet):
    permission_classes = (IsAuthenticated,)

    def create(self, request, account_id):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)

        serializer = serializers.StockTransactionSerializer(data=request.data, context={'account_id': account.id})
        serializer.is_valid(raise_exception=True)

        try:
            models.Stock.objects.get(pk=serializer.validated_data['isin'])
        except models.Stock.DoesNotExist:
            return Response({"error": "Stock not found."}, status=404)

        serializer.save()
        logging.info("Stock Transaction added")
        return Response({"msg": "Stock Transaction added"}, status=status.HTTP_201_CREATED)

    def list(self, request, account_id):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)

        stock_transactions = models.StockTransaction.objects.filter(account=account).order_by('-date')

        serializer = serializers.StockTransactionSerializer(stock_transactions, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


class StockSearchAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        query_string = request.GET['query_string']
        url = f'https://eodhd.com/api/search/{query_string}?api_token={EOD_TOKEN}'

        try:
            response = requests.get(url, timeout=30.0)
            data = response.json()
            return Response(data, status=response.status_code)
        except Exception as e:
            return Response({'error': 'Internal Server Error'}, status=500)
