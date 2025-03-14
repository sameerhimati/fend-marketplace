# Generated by Django 5.1.6 on 2025-03-01 15:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pilots', '0002_pilot_price_max_pilot_price_min_pilot_price_type_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='pilot',
            name='price_max',
        ),
        migrations.RemoveField(
            model_name='pilot',
            name='price_min',
        ),
        migrations.RemoveField(
            model_name='pilot',
            name='price_type',
        ),
        migrations.AddField(
            model_name='pilot',
            name='price',
            field=models.DecimalField(decimal_places=2, default=0, help_text='Enter the fixed price for this pilot (in USD)', max_digits=10),
        ),
    ]
