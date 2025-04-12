from django.core.management.base import BaseCommand
from apps.payments.models import PricingPlan

class Command(BaseCommand):
    help = 'Sets up the simplified pricing plans for Fend Marketplace'

    def handle(self, *args, **kwargs):
        plans_data = [
            {
                "name": "Startup Monthly",
                "plan_type": "startup_monthly",
                "price": 10.00,
                "billing_frequency": "monthly",
                "initial_tokens": 0,
                "is_active": True
            },
            {
                "name": "Startup Yearly",
                "plan_type": "startup_yearly",
                "price": 100.00,
                "billing_frequency": "yearly",
                "initial_tokens": 0,
                "is_active": True
            },
            {
                "name": "Enterprise Monthly",
                "plan_type": "enterprise_monthly",
                "price": 100.00,
                "billing_frequency": "monthly",
                "initial_tokens": 1,  # 1 token included with monthly plan
                "is_active": True
            },
            {
                "name": "Enterprise Yearly",
                "plan_type": "enterprise_yearly",
                "price": 1000.00,
                "billing_frequency": "yearly",
                "initial_tokens": 2,  # 2 tokens included with yearly plan
                "is_active": True
            }
        ]
        
        for plan_data in plans_data:
            plan_type = plan_data['plan_type']
            plan, created = PricingPlan.objects.update_or_create(
                plan_type=plan_type,
                defaults=plan_data
            )
            
            status = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f'{status} plan: {plan.name} (${plan.price})'))