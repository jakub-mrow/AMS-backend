# Generated by Django 4.0.10 on 2023-11-01 22:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ams', '0010_remove_accountpreferences_tax_value'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='xirr',
            field=models.DecimalField(blank=True, decimal_places=10, max_digits=17, null=True),
        ),
    ]