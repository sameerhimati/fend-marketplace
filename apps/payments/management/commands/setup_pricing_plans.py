from django.core.management.base import BaseCommand
from apps.payments.models import PricingPlan

class Command(BaseCommand):
    help = 'Sets up the pricing plans for Fend Marketplace'

    def handle(self, *args, **kwargs):
        plans_data = [
            {
                "name": "Startup Monthly",
                "plan_type": "startup_monthly",
                "price": 10.00,
                "billing_frequency": "monthly",
                "pilot_limit": None,  # Not applicable for startups
                "is_active": True
            },
            {
                "name": "Startup Yearly",
                "plan_type": "startup_yearly",
                "price": 100.00,
                "billing_frequency": "yearly",
                "pilot_limit": None,  # Not applicable for startups
                "is_active": True
            },
            {
                "name": "Enterprise Monthly",
                "plan_type": "enterprise_monthly",
                "price": 100.00,
                "billing_frequency": "monthly",
                "pilot_limit": 5,  # 5 pilots for monthly plan
                "is_active": True
            },
            {
                "name": "Enterprise Yearly",
                "plan_type": "enterprise_yearly",
                "price": 1000.00,
                "billing_frequency": "yearly",
                "pilot_limit": None,  # Unlimited pilots for yearly plan
                "is_active": True
            }
        ]
        
        for plan_data in plans_data:
            plan_type = plan_data.pop('plan_type')
            try:
                # Try to get existing plan
                plan = PricingPlan.objects.get(plan_type=plan_type)
                
                # Update fields
                for key, value in plan_data.items():
                    setattr(plan, key, value)
                
                plan.save()
                self.stdout.write(self.style.SUCCESS(f'Updated plan: {plan.name}'))
            except PricingPlan.DoesNotExist:
                # Create new plan
                plan_data['plan_type'] = plan_type
                plan = PricingPlan.objects.create(**plan_data)
                self.stdout.write(self.style.SUCCESS(f'Created plan: {plan.name}'))