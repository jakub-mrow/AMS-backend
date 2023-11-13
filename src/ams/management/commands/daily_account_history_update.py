from django.core.management.base import BaseCommand

from ...services import history_service


class Command(BaseCommand):
    help = 'Update Account History and Last Save Date'

    def handle(self, *args, **kwargs):
        history_service.save_account_history()
        self.stdout.write(self.style.SUCCESS('Successfully updated account history and last save date'))
