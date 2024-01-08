import datetime
import logging

from django.db import transaction
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action, parser_classes
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import get_object_or_404
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ams import models, serializers
from ams.permissions import IsObjectOwner
from ams.serializers import ExchangeSerializer
from ams.services import account_history_service, account_balance_service, \
    import_service, account_xirr_service
from ams.services import stock_balance_service, eod_service
from ams.services.account_balance_service import add_transaction_from_stock, add_transaction_to_account_balance
from ams.services.import_service import IncorrectFileFormatException, UnknownAssetException
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

        should_recalculate_xirr = False
        try:
            account_preferences = account.account_preferences
            if account_preferences.base_currency != serializer.validated_data.get('base_currency'):
                should_recalculate_xirr = True
            account_preferences.base_currency = serializer.validated_data.get('base_currency')
            account_preferences.tax_currency = serializer.validated_data.get('tax_currency')
            account_preferences.save()
        except models.AccountPreferences.DoesNotExist:
            should_recalculate_xirr = True
            serializer.save()

        if should_recalculate_xirr:
            account_xirr_service.calculate_account_xirr(account)

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
        add_transaction_to_account_balance(transaction, account)

        return Response({"msg": "Transaction created."}, status=status.HTTP_201_CREATED)

    def list(self, request, account_id):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)

        transactions = models.AccountTransaction.objects.filter(account=account).order_by('-date')

        transaction_type = self.request.query_params.get('transaction_type')
        if transaction_type in [models.AccountTransaction.DEPOSIT, models.AccountTransaction.WITHDRAWAL]:
            transactions = transactions.filter(transaction_type=transaction_type)
        serializer = serializers.TransactionSerializer(transactions, many=True)

        return Response(serializer.data)

    def update(self, request, account_id, pk=None):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)

        account_transaction = get_object_or_404(models.AccountTransaction, pk=pk, account=account)
        old_account_transaction_date = account_transaction.date

        serializer = serializers.TransactionSerializer(account_transaction, data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                account_transaction = serializer.save()
                account_balance_service.modify_transaction(account_transaction, old_account_transaction_date)
        except Exception as e:
            return Response({"error": "Account transaction not modified."}, status=400)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, account_id, pk=None):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)

        account_transaction = get_object_or_404(models.AccountTransaction, pk=pk, account=account)
        account_balance_service.delete_transaction(account_transaction)

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
        serializer.save(exchange=exchange, type="STOCK" if exchange.code != "CC" else "CRYPTO")
        logging.info("Stock added")
        return Response({"msg": "Stock added"}, status=status.HTTP_201_CREATED)

    def list(self, request, exchange_id=None):
        try:
            stocks = models.Asset.objects.filter(exchange=exchange_id)
        except models.Asset.DoesNotExist:
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
            stock = models.Asset.objects.get(pk=serializer.validated_data['asset_id'])
        except models.Asset.DoesNotExist:
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

        asset_id = self.request.query_params.get('id')
        if asset_id:
            stock_transactions = models.AssetTransaction.objects.filter(account=account, asset_id=asset_id).order_by('-date')
        else:
            stock_transactions = models.AssetTransaction.objects.filter(account=account).order_by('-date')
        stock_transactions = stock_transactions.filter(
            transaction_type__in=[models.AssetTransaction.BUY, models.AssetTransaction.SELL,
                                  models.AssetTransaction.DIVIDEND])

        serializer = serializers.StockTransactionSerializer(stock_transactions, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, account_id, pk=None):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)

        stock_transaction = get_object_or_404(models.AssetTransaction, pk=pk, account=account)
        stock_balance_service.delete_stock_transaction(stock_transaction)

        return Response(status=status.HTTP_204_NO_CONTENT)

    def update(self, request, account_id, pk=None):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)

        stock_transaction = get_object_or_404(models.AssetTransaction, pk=pk, account=account)
        old_stock_transaction_date = stock_transaction.date

        serializer = serializers.StockTransactionSerializer(stock_transaction, data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                stock_transaction = serializer.save()
                stock_balance_service.modify_stock_transaction(stock_transaction, old_stock_transaction_date)
        except Exception as e:
            return Response({"error": "Stock transaction not modified."}, status=400)

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

        stock_transactions = models.AssetTransaction.objects.filter(account=account).order_by('-date')

        serializer = serializers.StockTransactionSerializer(stock_transactions, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['GET'])
    def dto(self, request, pk, account_id):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)

        stock_balance = models.AssetBalance.objects.filter(asset_id=pk, account=account).first()
        serializer = serializers.StockBalanceDtoSerializer(stock_balance, many=False)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['GET'])
    def list_dto(self, request, account_id):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)

        stock_balances = models.AssetBalance.objects.filter(account=account)
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
            stock_balance_histories = models.AssetBalanceHistory.objects.filter(asset_id=pk, account=account,
                                                                                date__gte=from_date,
                                                                                date__lte=to_date).order_by('date')
        elif from_date:
            stock_balance_histories = models.AssetBalanceHistory.objects.filter(asset_id=pk, account=account,
                                                                                date__gte=from_date).order_by('date')
        elif to_date:
            stock_balance_histories = models.AssetBalanceHistory.objects.filter(asset_id=pk, account=account,
                                                                                date__lte=to_date).order_by('date')
        else:
            stock_balance_histories = models.AssetBalanceHistory.objects.filter(asset_id=pk, account=account).order_by(
                'date')
        serializer = serializers.StockBalanceHistoryDtoSerializer(stock_balance_histories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['GET'])
    def price(self, request, pk, account_id):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
            stock = models.Asset.objects.get(pk=pk)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)
        except models.Asset.DoesNotExist:
            return Response({"error": "Stock not found."}, status=404)

        stock_balance = models.AssetBalance.objects.filter(asset_id=pk, account=account).first()
        try:
            price, currency = stock_balance_service.get_stock_price_in_base_currency(stock_balance, stock)
            return Response({"price": price, "currency": currency}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(e)
            return Response({"error": "Problem with getting stock value"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FavoriteAssetViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, IsObjectOwner)
    serializer_class = serializers.FavoriteAssetSerializer
    queryset = models.FavoriteAsset.objects.all()

    def create(self, request, *args, **kwargs):
        request.data['user'] = request.user.id
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response({"msg": "Asset added to favourites"}, status=status.HTTP_201_CREATED)

    def list(self, request, *args, **kwargs):
        queryset = models.FavoriteAsset.objects.filter(user=request.user)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


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


class StockDetailsAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        stock = request.GET.get('stock')
        exchange = request.GET.get('exchange')
        period = request.GET.get('period', 'd')
        from_date = request.GET.get('from', datetime.datetime.now().date().strftime("%Y-%m-%d"))
        from_date = datetime.datetime.strptime(from_date, "%Y-%m-%d").date()
        to_date = request.GET.get('to', datetime.datetime.now().date().strftime("%Y-%m-%d"))
        to_date = datetime.datetime.strptime(to_date, "%Y-%m-%d").date()

        try:
            stock_details = eod_service.get_stock_details(stock, exchange, period, from_date, to_date)
            stock_details['exchange_info'] = serializers.ExchangeSerializer(stock_details['exchange_info']).data
            return Response(data=stock_details, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(e)
            return Response({'error': 'Internal Server Error'}, status=500)


class StockPriceHistoryAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        stock = request.GET.get('stock')
        exchange = request.GET.get('exchange')
        to_date = datetime.datetime.now().date().strftime("%Y-%m-%d")
        to_date = datetime.datetime.strptime(to_date, "%Y-%m-%d").date()

        try:
            stock_details = eod_service.get_stock_history(stock, exchange, None, to_date)

            return Response(data=stock_details, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(e)
            return Response({'error': 'Internal Server Error'}, status=500)


class StockNewsAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        stock = request.GET.get('stock')

        try:
            stock_news = eod_service.get_stock_news(stock)
            return Response(data=stock_news, status=status.HTTP_200_OK)
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


class AccountHistoryView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, account_id):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)

        dtos = account_history_service.get_account_history_dtos(account)

        serializer = serializers.AccountHistoryDtoSerializer(dtos, many=True)
        return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def stock_transactions(request):
    serializer = serializers.FileUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    file = serializer.validated_data['file']
    if file.content_type not in ["text/csv"]:
        return Response({"error": "File type not supported"}, status=status.HTTP_400_BAD_REQUEST)
    broker = request.query_params.get('broker')
    if not broker:
        return Response({"error": "Broker not specified"}, status=status.HTTP_400_BAD_REQUEST)
    strategy = import_service.get_strategy(broker, file)
    if not strategy:
        return Response({"error": "Broker not supported"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = strategy.convert()
    except UnknownAssetException as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except IncorrectFileFormatException:
        return Response({"error": "File has incorrect format"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception(e)
        return Response({"error": "Import failed"}, status=status.HTTP_400_BAD_REQUEST)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=TODO.csv'
    result.to_csv(response, header=False, index=False)
    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def csv_stock_transactions(request, account_id):
    try:
        account = models.Account.objects.get(pk=account_id, user=request.user)
    except models.Account.DoesNotExist:
        return Response({"error": "Account not found."}, status=404)
    serializer = serializers.FileUploadSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    file = serializer.validated_data['file']
    if file.content_type not in ["text/csv"]:
        return Response({"error": "File type not supported"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        import_service.import_csv(file, account)
    except IncorrectFileFormatException:
        return Response({"error": "File has incorrect format"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception(e)
        return Response({"error": "Import failed"}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"msg": "Import successful"}, status=status.HTTP_200_OK)
