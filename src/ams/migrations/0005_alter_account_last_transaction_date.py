# Generated by Django 4.0.10 on 2023-09-20 17:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ams', '0004_alter_transaction_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='account',
            name='last_transaction_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]