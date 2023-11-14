import datetime
import logging

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ams import models, serializers
from ams.permissions import IsObjectOwner
from ams.serializers import ExchangeSerializer
from ams.services import stock_balance_service, eod_service
from ams.services.account_balance_service import add_transaction_from_stock, rebuild_account_balance, \
    add_transaction_to_account_balance
from ams.services.stock_balance_service import update_stock_price

logger = logging.getLogger(__name__)
logging.getLogger("urllib3").setLevel(logging.WARNING)


class AccountViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.AccountCreateSerializer
    permission_classes = (IsAuthenticated, IsObjectOwner)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = serializer.save()
        models.AccountPreferences.objects.create(
            account=account,
            base_currency='PLN',
            tax_currency='PLN',
        )
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

    @action(detail=True, methods=['PUT'])
    def set_preferences(self, request, pk=None):
        account = self.get_object()
        serializer = serializers.AccountPreferencesSerializer(data=request.data, context={'account_id': account.id})
        serializer.is_valid(raise_exception=True)

        try:
            account_preferences = account.account_preferences
            account_preferences.base_currency = serializer.validated_data.get('base_currency')
            account_preferences.tax_value = serializer.validated_data.get('tax_value')
            account_preferences.tax_currency = serializer.validated_data.get('tax_currency')
            account_preferences.save()
        except models.AccountPreferences.DoesNotExist:
            serializer.save()

        return Response({"msg": "Account preferences updated"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['GET'])
    def get_preferences(self, request, pk=None):
        account = self.get_object()
        try:
            preferences = account.account_preferences
        except models.AccountPreferences.DoesNotExist:
            preferences = None

        if preferences:
            return Response(serializers.AccountPreferencesSerializer(account.account_preferences).data,
                            status=status.HTTP_200_OK)
        else:
            return Response({"error": "No preferences found for to this account"},
                            status=status.HTTP_404_NOT_FOUND)


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

        if account.last_save_date and account.last_transaction_date.date:
            if account.last_transaction_date.date() > transaction.date.date() > account.last_save_date.date():
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
            stock = models.Stock.objects.get(pk=serializer.validated_data['isin'])
        except models.Stock.DoesNotExist:
            return Response({"error": "Stock not found."}, status=404)

        try:
            with transaction.atomic():
                stock_transaction = serializer.save()
                stock_balance_service.add_stock_transaction_to_balance(stock_transaction, stock, account)
                add_transaction_from_stock(stock_transaction, stock, account)
        except Exception as e:
            return Response({"error": str(e)}, status=400)

        logging.info("Stock Transaction added")
        return Response({"msg": "Stock Transaction added"}, status=status.HTTP_201_CREATED)

    def list(self, request, account_id):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)

        isin = self.request.query_params.get('isin')
        if isin:
            stock_transactions = models.StockTransaction.objects.filter(account=account, isin=isin).order_by('-date')
        else:
            stock_transactions = models.StockTransaction.objects.filter(account=account).order_by('-date')
        stock_transactions = stock_transactions.filter(transaction_type__in=['buy', 'sell'])

        serializer = serializers.StockTransactionSerializer(stock_transactions, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['POST'])
    def buy(self, request, account_id):
        serializer = serializers.BuyCommandSerializer(data=request.data, context={'account_id': account_id})
        serializer.is_valid(raise_exception=True)
        buy_command = serializer.save()
        try:
            stock_balance_service.buy_stocks(buy_command)
        except Exception as e:
            logger.exception(e)
            return Response({"error": f"Problem with buying stocks"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"msg": f"Stocks ${buy_command.ticker} bought"}, status=status.HTTP_201_CREATED)


class StockBalanceViewSet(viewsets.ViewSet):
    permission_classes = (IsAuthenticated,)

    def list(self, request, account_id):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)

        stock_transactions = models.StockTransaction.objects.filter(account=account).order_by('-date')

        serializer = serializers.StockTransactionSerializer(stock_transactions, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['GET'])
    def dto(self, request, pk, account_id):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)

        stock_balance = models.StockBalance.objects.filter(isin=pk, account=account).first()
        serializer = serializers.StockBalanceDtoSerializer(stock_balance, many=False)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['GET'])
    def list_dto(self, request, account_id):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)

        stock_balances = models.StockBalance.objects.filter(account=account)
        serializer = serializers.StockBalanceDtoSerializer(stock_balances, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['GET'])
    def history(self, request, pk, account_id):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)

        from_date = request.query_params.get('from')
        to_date = request.query_params.get('to')

        if from_date and to_date:
            stock_balance_histories = models.StockBalanceHistory.objects.filter(isin=pk, account=account,
                                                                                date__gte=from_date,
                                                                                date__lte=to_date).order_by('date')
        elif from_date:
            stock_balance_histories = models.StockBalanceHistory.objects.filter(isin=pk, account=account,
                                                                                date__gte=from_date).order_by('date')
        elif to_date:
            stock_balance_histories = models.StockBalanceHistory.objects.filter(isin=pk, account=account,
                                                                                date__lte=to_date).order_by('date')
        else:
            stock_balance_histories = models.StockBalanceHistory.objects.filter(isin=pk, account=account).order_by(
                'date')
        serializer = serializers.StockBalanceHistoryDtoSerializer(stock_balance_histories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class StockSearchAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        query_string = request.GET['query_string']

        try:
            data = eod_service.search(query_string)
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(e)
            return Response({'error': 'Internal Server Error'}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_stock(request):
    if request.data.get('date'):
        update_stock_price(datetime.datetime.fromisoformat(request.data.get('date')))
    else:
        update_stock_price()
    return Response({"msg": "Stock price updated"}, status=status.HTTP_200_OK)
