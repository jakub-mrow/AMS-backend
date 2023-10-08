# Generated by Django 4.0.10 on 2023-09-14 20:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ams', '0002_account_accountbalance_accounthistory_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='last_save_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='account',
            name='last_transaction_date',
            field=models.DateTimeField(default='2023-09-13T10:30:00.123456Z'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='transaction',
            name='correlation_id',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]