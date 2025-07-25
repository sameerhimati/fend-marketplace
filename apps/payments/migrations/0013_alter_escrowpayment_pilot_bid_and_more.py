# Generated by Django 5.2.1 on 2025-06-25 21:17

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0012_alter_escrowpayment_status'),
        ('pilots', '0012_remove_pilot_admin_verified_at_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='escrowpayment',
            name='pilot_bid',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='payment_holding_service', to='pilots.pilotbid'),
        ),
        migrations.DeleteModel(
            name='PilotTransaction',
        ),
    ]
