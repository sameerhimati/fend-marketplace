# Generated by Django 5.1.6 on 2025-03-01 18:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pilots', '0003_remove_pilot_price_max_remove_pilot_price_min_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='pilotbid',
            name='fee_percentage',
            field=models.DecimalField(decimal_places=2, default=5.0, help_text='Transaction fee percentage', max_digits=5),
        ),
        migrations.AlterField(
            model_name='pilotbid',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('under_review', 'Under Review'), ('approved', 'Approved'), ('declined', 'Declined'), ('completed', 'Completed'), ('paid', 'Paid')], default='pending', max_length=20),
        ),
    ]
