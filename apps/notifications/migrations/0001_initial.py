# Generated by Django 5.1.6 on 2025-02-19 21:39

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('pilots', '0002_pilot_price_max_pilot_price_min_pilot_price_type_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('bid_submitted', 'New Bid Submitted'), ('bid_updated', 'Bid Status Updated'), ('pilot_updated', 'Pilot Updated'), ('payment_received', 'Payment Received')], max_length=20)),
                ('title', models.CharField(max_length=255)),
                ('message', models.TextField()),
                ('read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL)),
                ('related_bid', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='pilots.pilotbid')),
                ('related_pilot', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='pilots.pilot')),
            ],
        ),
    ]
