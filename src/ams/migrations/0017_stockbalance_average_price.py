# Generated by Django 4.0.10 on 2023-11-29 16:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ams', '0016_merge_20231111_1709'),
    ]

    operations = [
        migrations.AddField(
            model_name='stockbalance',
            name='average_price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=13),
            preserve_default=False,
        ),
    ]