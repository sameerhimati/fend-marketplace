import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fend.settings.base')
django.setup()

# Import models after setting up Django
from apps.payments.models import PricingPlan, TokenPackage

def create_pricing_plans():
    # Define plan data
    plans_data = [
        {
            "name": "Startup Monthly",
            "plan_type": "startup_monthly",
            "price": 10.00,
            "billing_frequency": "monthly",
            "pilot_limit": 0,
            "is_active": True
        },
        {
            "name": "Startup Yearly",
            "plan_type": "startup_yearly",
            "price": 100.00,
            "billing_frequency": "yearly",
            "pilot_limit": 0,
            "is_active": True
        },
        {
            "name": "Enterprise Monthly",
            "plan_type": "enterprise_monthly",
            "price": 100.00,
            "billing_frequency": "monthly",
            "pilot_limit": 0,  # No pilot limit - using tokens instead
            "is_active": True
        },
        {
            "name": "Enterprise Yearly",
            "plan_type": "enterprise_yearly",
            "price": 1000.00,
            "billing_frequency": "yearly",
            "pilot_limit": 0,  # No pilot limit - using tokens instead
            "is_active": True
        }
    ]
    
    # Update or create plans
    for plan_data in plans_data:
        plan_type = plan_data.pop('plan_type')
        try:
            plan = PricingPlan.objects.get(plan_type=plan_type)
            # Update existing plan fields
            for key, value in plan_data.items():
                setattr(plan, key, value)
            # Don't reset stripe_price_id if it exists
            plan.save()
            print(f"Updated plan: {plan.name}")
        except PricingPlan.DoesNotExist:
            # Create new plan
            plan_data['plan_type'] = plan_type
            plan_data['stripe_price_id'] = ""  # Set empty string for new plans
            PricingPlan.objects.create(**plan_data)
            print(f"Created plan: {plan_data['name']}")
    
    print(f"Pricing plans updated successfully")

def create_token_packages():
    # Check if there are already token packages
    if TokenPackage.objects.exists():
        print("Token packages already exist. Updating existing packages.")
        
    # Define token packages
    packages = [
        {
            "name": "Token",
            "token_count": 1,
            "price": 100.00,
            "description": "Single token for publishing one pilot opportunity",
            "is_active": True
        }
    ]
    
    # Update or create token packages
    for package_data in packages:
        name = package_data['name']
        try:
            package = TokenPackage.objects.get(name=name)
            # Update existing package fields
            for key, value in package_data.items():
                setattr(package, key, value)
            # Don't reset stripe_price_id if it exists
            package.save()
            print(f"Updated token package: {package.name}")
        except TokenPackage.DoesNotExist:
            # Create new package
            TokenPackage.objects.create(**package_data)
            print(f"Created token package: {name}")
    
    print(f"Token packages updated successfully")

if __name__ == "__main__":
    create_pricing_plans()
    create_token_packages()