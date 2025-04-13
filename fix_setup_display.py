import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fend.settings.base')
django.setup()

# Import models
from apps.organizations.models import Organization
from apps.payments.models import PricingPlan, Subscription
from django.utils import timezone
from datetime import timedelta

def fix_startup_display():
    """Ensure all startups have correctly displayed subscription status"""
    startups = Organization.objects.filter(type='startup')
    
    print(f"Checking {startups.count()} startups for display issues...")
    
    for startup in startups:
        try:
            # Get the subscription 
            subscription = Subscription.objects.get(organization=startup)
            
            # Check if subscription has period dates
            if not subscription.current_period_start or not subscription.current_period_end:
                print(f"  Fixing display dates for {startup.name}")
                # Set proper display dates for UI
                subscription.current_period_start = timezone.now() - timedelta(days=1)
                subscription.current_period_end = timezone.now() + timedelta(days=29)
                subscription.save()
                
            # Ensure startups have active status
            if subscription.status != 'active':
                print(f"  Fixing status for {startup.name}")
                subscription.status = 'active'
                subscription.save()
                
        except Subscription.DoesNotExist:
            # Skip - this will be handled by other scripts
            pass

if __name__ == "__main__":
    fix_startup_display()