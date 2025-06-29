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
            plan_type='enterprise_monthly',
            price=100.00,
            billing_frequency='monthly',
            stripe_price_id='temp_enterprise_monthly',
            pilot_limit=5,
            is_active=True
        )
        self.stdout.write(f'Created: {enterprise_monthly.name}')

        enterprise_yearly = PricingPlan.objects.create(
            name='Enterprise Yearly', 
            plan_type='enterprise_yearly',
            price=1000.00,
            billing_frequency='yearly',
            stripe_price_id='temp_enterprise_yearly',
            pilot_limit=None,  # Unlimited
            is_active=True
        )
        self.stdout.write(f'Created: {enterprise_yearly.name}')

        # Create Startup Plans
        startup_monthly = PricingPlan.objects.create(
            name='Startup Monthly',
            plan_type='startup_monthly', 
            price=10.00,
            billing_frequency='monthly',
            stripe_price_id='temp_startup_monthly',
            pilot_limit=None,  # Unlimited bids
            is_active=True
        )
        self.stdout.write(f'Created: {startup_monthly.name}')

        startup_yearly = PricingPlan.objects.create(
            name='Startup Yearly',
            plan_type='startup_yearly',
            price=100.00,
            billing_frequency='yearly',
            stripe_price_id='temp_startup_yearly',
            pilot_limit=None,  # Unlimited bids
            is_active=True
        )
        self.stdout.write(f'Created: {startup_yearly.name}')

        self.stdout.write(
            self.style.SUCCESS('Successfully created default pricing plans!')
        )