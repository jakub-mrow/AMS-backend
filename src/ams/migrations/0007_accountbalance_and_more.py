# Generated by Django 4.0.10 on 2023-08-07 14:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ams', '0006_alter_account_unique_together_account_name_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccountBalance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('currency', models.CharField(max_length=10)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=17)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='balances', to='ams.account')),
            ],
        ),
        migrations.RenameField(
            model_name='transaction',
            old_name='transaction_type',
            new_name='type',
        ),
        migrations.AddField(
            model_name='transaction',
            name='currency',
            field=models.CharField(default='EUR', max_length=10),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='transaction',
            name='amount',
            field=models.DecimalField(decimal_places=2, max_digits=17),
        ),
        migrations.DeleteModel(
            name='Task',
        ),
    ]