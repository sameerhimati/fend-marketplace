# Generated manually to rename EscrowPayment to PaymentHoldingService

from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('payments', '0016_alter_freeaccountcode_options'),
    ]

    operations = [
        # Rename the model
        migrations.RenameModel(
            old_name='EscrowPayment',
            new_name='PaymentHoldingService',
        ),
        # Rename the model
        migrations.RenameModel(
            old_name='EscrowPaymentLog',
            new_name='PaymentHoldingServiceLog',
        ),
        # Rename field in PaymentHoldingServiceLog
        migrations.RenameField(
            model_name='PaymentHoldingServiceLog',
            old_name='escrow_payment',
            new_name='payment_holding_service',
        ),
        # Update related_name in logs field
        migrations.AlterField(
            model_name='PaymentHoldingServiceLog',
            name='payment_holding_service',
            field=models.ForeignKey(
                on_delete=models.CASCADE,
                related_name='logs',
                to='payments.PaymentHoldingService'
            ),
        ),
    ]