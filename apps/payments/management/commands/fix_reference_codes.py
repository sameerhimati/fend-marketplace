
from django.core.management.base import BaseCommand
from apps.payments.models import EscrowPayment
from django.utils import timezone

class Command(BaseCommand):
    help = 'Fixes missing reference codes for escrow payments'

    def handle(self, *args, **kwargs):
        payments = EscrowPayment.objects.filter(reference_code__isnull=True) | EscrowPayment.objects.filter(reference_code='')
        
        if not payments.exists():
            self.stdout.write(self.style.SUCCESS('No payments with missing reference codes found'))
            return
            
        self.stdout.write(f'Found {payments.count()} payments with missing reference codes')
        
        for payment in payments:
            prefix = "FND-PILOT"
            bid_id = payment.pilot_bid.id
            timestamp = int(timezone.now().timestamp())
            payment.reference_code = f"{prefix}-{bid_id}-{timestamp}"
            payment.save()
            self.stdout.write(f'  Fixed payment ID {payment.id} with new code: {payment.reference_code}')
            
        self.stdout.write(self.style.SUCCESS('Successfully fixed all reference codes'))