import logging

from ams import models, serializers

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import permission_classes, api_view
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .permissions import IsObjectOwner
from .serializers import ExchangeSerializer

logger = logging.getLogger(__name__)


class TaskViewSet(viewsets.ModelViewSet):
    """
    Return information about task.
    """
    serializer_class = serializers.TaskSerializer
    permission_classes = (IsAuthenticated, )
    queryset = models.Task.objects.all()

    def create(self, request):
        """
        Submit a new task.
        """
        user = self.request.user
        task_serializer = serializers.TaskSerializer(data=request.data)
        task_serializer.is_valid(raise_exception=True)

        logging.info("Creating task")
        task = models.Task()
        task.user = user
        task.description = request.data.get("description", "")
        task.save()
        logging.info("Task created")

        return Response({"msg": "Task created"}, status=status.HTTP_201_CREATED)


    def list(self, request):
        """
        List all the tasks.
        """
        user = self.request.user
        qs = models.Task.objects.filter(user=user)
        task_serializer = serializers.TaskSerializer(qs, many=True)

        return Response(task_serializer.data, status=status.HTTP_200_OK)


class AccountViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.AccountCreateSerializer
    permission_classes = (IsAuthenticated, IsObjectOwner)

    def create(self, request, *args, **kwargs):
        """
        Create a new account.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(balance=0)
        logging.info("Account created")
        return Response({"msg": "Account created"}, status=status.HTTP_201_CREATED)

    def get_queryset(self):
        return models.Account.objects.filter(user=self.request.user).order_by('currency')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return serializers.AccountCreateSerializer
        return serializers.AccountSerializer


class DepositViewSet(viewsets.ViewSet):
    permission_classes = (IsAuthenticated, )

    def create(self, request, account_id):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)

        serializer = serializers.DepositSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data['amount']
        account.balance += amount
        account.save()

        models.Transaction.objects.create(account=account, transaction_type=models.Transaction.DEPOSIT, amount=amount)

        return Response({"message": "Deposit transaction created successfully."}, status=201)


class WithdrawalViewSet(viewsets.ViewSet):
    permission_classes = (IsAuthenticated, )

    def create(self, request, account_id):
        try:
            account = models.Account.objects.get(pk=account_id, user=request.user)
        except models.Account.DoesNotExist:
            return Response({"error": "Account not found."}, status=404)

        serializer = serializers.WithdrawalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data['amount']
        if account.balance < amount:
            return Response({"error": "Insufficient balance."}, status=400)

        account.balance -= amount
        account.save()

        models.Transaction.objects.create(account=account, transaction_type=models.Transaction.WITHDRAWAL,
                                          amount=amount)

        return Response({"message": "Withdrawal transaction created successfully."}, status=201)


class TransactionViewSet(viewsets.ViewSet):
    permission_classes = (IsAuthenticated, )

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


class ExchangeViewSet(viewsets.ViewSet):
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

    def create(self, request):
        try :
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
