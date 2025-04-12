import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fend.settings.base')
django.setup()

# Import models after setting up Django
from apps.payments.models import PricingPlan, TokenPackage

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
            "name": "Enterprise Monthly",
            "plan_type": "enterprise_monthly",
            "price": 50.00,
            "billing_frequency": "monthly",
            "stripe_price_id": "",
            "pilot_limit": 0,  # No pilot limit - using tokens instead
            "is_active": True
        },
        {
            "name": "Enterprise Yearly",
            "plan_type": "enterprise_yearly",
            "price": 500.00,
            "billing_frequency": "yearly",
            "stripe_price_id": "",
            "pilot_limit": 0,  # No pilot limit - using tokens instead
            "is_active": True
        }
    ]
    
    for plan_data in plans:
        PricingPlan.objects.create(**plan_data)
    
    print(f"Created {len(plans)} pricing plans")

def create_token_packages():
    # Check if there are already token packages
    if TokenPackage.objects.exists():
        print("Token packages already exist. Skipping creation.")
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
        
    print(f"Created {len(packages)} token packages")

if __name__ == "__main__":
    create_pricing_plans()
    create_token_packages()