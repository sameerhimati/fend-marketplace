from django.core.management.base import BaseCommand
from apps.payments.models import TokenPackage

class Command(BaseCommand):
    help = 'Creates the default token package for the marketplace'

    def handle(self, *args, **kwargs):
        package, created = TokenPackage.objects.get_or_create(
            name="Standard Token",
            defaults={
                "price_per_token": 100.00,
                "description": "Tokens for publishing pilot opportunities",
                "is_active": True
            }
        )
        
        status = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f'{status} default token package: ${package.price_per_token} per token'))