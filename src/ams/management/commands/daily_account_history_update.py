from django.core.management.base import BaseCommand
from django.utils import timezone

from ...models import Account, AccountHistory, AccountHistoryBalance, AccountBalance


class Command(BaseCommand):
    help = 'Update Account History and Last Save Date'

    def handle(self, *args, **kwargs):
        current_date = timezone.now().date()

        # Get all accounts
        accounts = Account.objects.all()

        for account in accounts:

            history_date = current_date - timezone.timedelta(days=1)
            account_history = AccountHistory.objects.create(account=account, date=history_date)
            account_balances = AccountBalance.objects.filter(account=account).all()

            for balance in account_balances:
                AccountHistoryBalance.objects.create(
                    account_history=account_history,
                    amount=balance.amount,
                    currency=balance.currency
                )

            account.last_save_date = history_date
            account.save()

        self.stdout.write(self.style.SUCCESS('Successfully updated account history and last save date'))