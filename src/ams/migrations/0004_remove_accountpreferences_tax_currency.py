# Generated by Django 4.0.10 on 2024-01-08 17:15

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ams', '0003_rename_transaction_accounttransaction_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='accountpreferences',
            name='tax_currency',
        ),
    ]