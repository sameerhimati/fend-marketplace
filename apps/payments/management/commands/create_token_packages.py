from django.core.management.base import BaseCommand
from apps.payments.models import TokenPackage

class Command(BaseCommand):
    help = 'Creates initial token packages for the marketplace'

    def handle(self, *args, **kwargs):
        # Check if there are already token packages
        if TokenPackage.objects.exists():
            self.stdout.write(self.style.WARNING('Token packages already exist. Skipping creation.'))
            return
            
        # Create token packages
        packages = [
            {
                "name": "Basic",
                "token_count": 1,
                "price": 199.00,
                "description": "Single token for publishing one pilot opportunity",
            },
            {
                "name": "Standard",
                "token_count": 5,
                "price": 899.00,
                "description": "5 tokens for publishing multiple pilot opportunities. Save $96!",
            },
            {
                "name": "Premium",
                "token_count": 10,
                "price": 1699.00,
                "description": "10 tokens for publishing multiple pilot opportunities. Save $291!",
            }
        ]
        
        for package_data in packages:
            TokenPackage.objects.create(**package_data)
            
        self.stdout.write(self.style.SUCCESS(f'Successfully created {len(packages)} token packages'))