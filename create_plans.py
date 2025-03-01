import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fend.settings.base')
django.setup()

# Import the model after setting up Django
from apps.payments.models import PricingPlan

def create_pricing_plans():
    # Clear existing plans
    PricingPlan.objects.all().delete()
    
    # Create plans
    plans = [
        {
            "name": "Startup Monthly",
            "plan_type": "startup_monthly",
            "price": 10.00,
            "billing_frequency": "monthly",
            "stripe_price_id": "",
            "pilot_limit": 0,
            "is_active": True
        },
        {
            "name": "Startup Yearly",
            "plan_type": "startup_yearly",
            "price": 100.00,
            "billing_frequency": "yearly",
            "stripe_price_id": "",
            "pilot_limit": 0,
            "is_active": True
        },
        {
            "name": "Enterprise Single Pilot",
            "plan_type": "enterprise_single",
            "price": 1000.00,
            "billing_frequency": "one_time",
            "stripe_price_id": "",
            "pilot_limit": 1,
            "is_active": True
        },
        {
            "name": "Enterprise Unlimited",
            "plan_type": "enterprise_unlimited",
            "price": 600.00,
            "billing_frequency": "yearly",
            "stripe_price_id": "",
            "pilot_limit": 0,
            "is_active": True
        }
    ]
    
    for plan_data in plans:
        PricingPlan.objects.create(**plan_data)
    
    print(f"Created {len(plans)} pricing plans")

if __name__ == "__main__":
    create_pricing_plans()