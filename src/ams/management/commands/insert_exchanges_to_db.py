import json
from django.core.management.base import BaseCommand, CommandError
from ams.models import Exchange
from django.utils.dateparse import parse_time
import os


class Command(BaseCommand):
    help = 'Load a list of exchanges from a JSON file into the database'

    def handle(self, *args, **options):

        try:
            with open('/code/src/ams/data/exchanges.json', 'r', encoding='utf-8') as file:
                data = json.load(file)
                for entry in data:
                    exchange, created = Exchange.objects.update_or_create(
                        name=entry['name'],
                        mic=entry['mic'].split(' ')[0],
                        defaults={
                            'country': entry['country'],
                            'code': entry['mic'].split(' ')[0],
                            'timezone': entry['timezone'],
                            'opening_hour': parse_time(entry['open']),
                            'closing_hour': parse_time(entry['close'])
                        }
                    )

                    if created:
                        self.stdout.write(self.style.SUCCESS(f'Successfully created exchange {exchange}'))
                    else:
                        self.stdout.write(self.style.WARNING(f'Updated existing exchange {exchange}'))

        except FileNotFoundError:
            raise CommandError(f'The file does not exist.')
        except json.JSONDecodeError as exc:
            raise CommandError(f'Invalid JSON format in the file: {exc}')
        except Exception as exc:
            raise CommandError(f'An error occurred: {exc}')
