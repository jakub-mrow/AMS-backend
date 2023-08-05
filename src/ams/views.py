import logging

from ams import models, serializers
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .permissions import IsObjectOwner

logger = logging.getLogger(__name__)


class AccountViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.AccountCreateSerializer
    permission_classes = (IsAuthenticated, IsObjectOwner)

    def create(self, request, *args, **kwargs):
        """
        Create a new account.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logging.info("Account created")
        return Response({"msg": "Account created"}, status=status.HTTP_201_CREATED)

    def get_queryset(self):
        return models.Account.objects.filter(user=self.request.user).order_by('id')

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
