import logging

from ams import models, serializers
from rest_framework import status, viewsets, generics
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .permissions import IsObjectOwner

logger = logging.getLogger(__name__)


class AccountViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.AccountCreateSerializer
    permission_classes = (IsAuthenticated, IsObjectOwner)

    def create(self, request, *args, **kwargs):
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

        if transaction.type == 'deposit':
            account_balance.amount += transaction.amount
        elif transaction.type == 'withdrawal':
            account_balance.amount -= transaction.amount

        if transaction.date > account.last_transaction_date:
            account.last_transaction_date = transaction.date

        account.save()
        account_balance.save()

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
