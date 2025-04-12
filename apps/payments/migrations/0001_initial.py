# Generated by Django 5.1.6 on 2025-04-12 21:05

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        #('organizations', '0005_initialize_tokens'),
        ('pilots', '0005_add_token_tracking'),
    ]

    operations = [
        migrations.CreateModel(
            name='PricingPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('plan_type', models.CharField(choices=[('startup_monthly', 'Startup Monthly'), ('startup_yearly', 'Startup Yearly'), ('enterprise_monthly', 'Enterprise Monthly'), ('enterprise_yearly', 'Enterprise Yearly')], max_length=50)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('billing_frequency', models.CharField(choices=[('monthly', 'Monthly'), ('yearly', 'Yearly')], max_length=20)),
                ('stripe_price_id', models.CharField(max_length=100)),
                ('initial_tokens', models.IntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'db_table': 'payments_pricingplan',
            },
        ),
        migrations.CreateModel(
            name='TokenPackage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('price_per_token', models.DecimalField(decimal_places=2, max_digits=10)),
                ('description', models.TextField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('stripe_price_id', models.CharField(blank=True, max_length=100, null=True)),
            ],
            options={
                'ordering': ['price_per_token'],
            },
        ),
        migrations.CreateModel(
            name='PilotTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('fee_amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('fee_percentage', models.DecimalField(decimal_places=2, default=5.0, max_digits=5)),
                ('stripe_payment_intent_id', models.CharField(max_length=100)),
                ('status', models.CharField(default='pending', max_length=20)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('pilot_bid', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='transaction', to='pilots.pilotbid')),
            ],
        ),
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stripe_subscription_id', models.CharField(blank=True, max_length=100, null=True)),
                ('stripe_customer_id', models.CharField(max_length=100)),
                ('status', models.CharField(choices=[('active', 'Active'), ('past_due', 'Past Due'), ('canceled', 'Canceled'), ('trialing', 'Trialing'), ('incomplete', 'Incomplete'), ('incomplete_expired', 'Incomplete Expired'), ('unpaid', 'Unpaid')], default='incomplete', max_length=20)),
                ('current_period_start', models.DateTimeField(blank=True, null=True)),
                ('current_period_end', models.DateTimeField(blank=True, null=True)),
                ('cancel_at_period_end', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organization', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='subscription', to='organizations.organization')),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='subscriptions', to='payments.pricingplan')),
            ],
        ),
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payment_type', models.CharField(choices=[('subscription', 'Subscription'), ('pilot_fee', 'Pilot Fee')], max_length=20)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('stripe_payment_id', models.CharField(max_length=100)),
                ('status', models.CharField(default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='organizations.organization')),
                ('subscription', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payments', to='payments.subscription')),
            ],
        ),
        migrations.CreateModel(
            name='TokenConsumptionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tokens_consumed', models.IntegerField(default=1)),
                ('action_type', models.CharField(choices=[('pilot_publish', 'Pilot Publication'), ('other', 'Other Consumption')], default='pilot_publish', max_length=50)),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='token_consumption_logs', to='organizations.organization')),
                ('pilot', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='token_consumptions', to='pilots.pilot')),
            ],
        ),
        migrations.CreateModel(
            name='TokenTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_count', models.IntegerField()),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('stripe_payment_id', models.CharField(max_length=100)),
                ('stripe_checkout_id', models.CharField(blank=True, max_length=100, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('completed', 'Completed'), ('cancelled', 'Cancelled'), ('failed', 'Failed')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='token_transactions', to='organizations.organization')),
                ('package', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transactions', to='payments.tokenpackage')),
            ],
        ),
    ]
