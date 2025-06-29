from django.core.management.base import BaseCommand
from apps.payments.models import PricingPlan


class Command(BaseCommand):
    help = 'Create default pricing plans for the platform'

    def handle(self, *args, **options):
        self.stdout.write('Creating default pricing plans...')
        
        # Check if plans already exist
        if PricingPlan.objects.exists():
            self.stdout.write(
                self.style.WARNING('Pricing plans already exist. Skipping creation.')
            )
            return
        
        # Create Enterprise Plans
        enterprise_monthly = PricingPlan.objects.create(
            name='Enterprise Monthly',
            plan_type='enterprise',
            price=100.00,
            pilot_limit=5,
            is_active=True,
            description='5 pilots per month'
        )
        self.stdout.write(f'Created: {enterprise_monthly.name}')

        enterprise_yearly = PricingPlan.objects.create(
            name='Enterprise Yearly', 
            plan_type='enterprise',
            price=1000.00,
            pilot_limit=None,  # Unlimited
            is_active=True,
            description='Unlimited pilots per year'
        )
        self.stdout.write(f'Created: {enterprise_yearly.name}')

        # Create Startup Plans
        startup_monthly = PricingPlan.objects.create(
            name='Startup Monthly',
            plan_type='startup', 
            price=10.00,
            pilot_limit=None,  # Unlimited bids
            is_active=True,
            description='Unlimited bids per month'
        )
        self.stdout.write(f'Created: {startup_monthly.name}')

        startup_yearly = PricingPlan.objects.create(
            name='Startup Yearly',
            plan_type='startup',
            price=100.00,
            pilot_limit=None,  # Unlimited bids
            is_active=True,
            description='Unlimited bids per year'
        )
        self.stdout.write(f'Created: {startup_yearly.name}')

        self.stdout.write(
            self.style.SUCCESS('Successfully created default pricing plans!')
        )