from django.core.management.base import BaseCommand
from apps.payments.models import PricingPlan, Subscription
from django.db import transaction

class Command(BaseCommand):
    help = 'Migrates existing subscriptions to new pricing structure'

    def handle(self, *args, **kwargs):
        # First, create or update the new plans
        with transaction.atomic():
            # Create new plans
            enterprise_monthly, _ = PricingPlan.objects.update_or_create(
                plan_type='enterprise_monthly',
                defaults={
                    'name': 'Enterprise Monthly',
                    'price': 100.00,
                    'billing_frequency': 'monthly',
                    'initial_tokens': 1,
                    'is_active': True
                }
            )
            
            enterprise_yearly, _ = PricingPlan.objects.update_or_create(
                plan_type='enterprise_yearly',
                defaults={
                    'name': 'Enterprise Yearly',
                    'price': 1000.00,
                    'billing_frequency': 'yearly', 
                    'initial_tokens': 2,
                    'is_active': True
                }
            )
            
            startup_monthly, _ = PricingPlan.objects.update_or_create(
                plan_type='startup_monthly',
                defaults={
                    'name': 'Startup Monthly',
                    'price': 10.00,
                    'billing_frequency': 'monthly',
                    'initial_tokens': 0,
                    'is_active': True
                }
            )
            
            startup_yearly, _ = PricingPlan.objects.update_or_create(
                plan_type='startup_yearly',
                defaults={
                    'name': 'Startup Yearly',
                    'price': 100.00,
                    'billing_frequency': 'yearly',
                    'initial_tokens': 0,
                    'is_active': True
                }
            )
            
            # Get existing subscriptions using old plans
            try:
                unlimited_plan = PricingPlan.objects.get(plan_type='enterprise_unlimited')
                unlimited_subs = Subscription.objects.filter(plan=unlimited_plan)
                self.stdout.write(f"Found {unlimited_subs.count()} subscriptions to migrate from Enterprise Unlimited")
                
                # Migrate Enterprise Unlimited to Enterprise Yearly
                for sub in unlimited_subs:
                    sub.plan = enterprise_yearly
                    sub.save()
                    self.stdout.write(f"Migrated subscription for {sub.organization.name} to Enterprise Yearly")
            except PricingPlan.DoesNotExist:
                self.stdout.write("No Enterprise Unlimited plan found")

            try:
                single_plan = PricingPlan.objects.get(plan_type='enterprise_single')
                single_subs = Subscription.objects.filter(plan=single_plan)
                self.stdout.write(f"Found {single_subs.count()} subscriptions to migrate from Enterprise Single")
                
                # Migrate Enterprise Single to Enterprise Monthly
                for sub in single_subs:
                    sub.plan = enterprise_monthly
                    sub.save()
                    self.stdout.write(f"Migrated subscription for {sub.organization.name} to Enterprise Monthly")
            except PricingPlan.DoesNotExist:
                self.stdout.write("No Enterprise Single plan found")

            # Deactivate old plans instead of deleting them
            for old_plan_type in ['enterprise_unlimited', 'enterprise_single']:
                try:
                    old_plan = PricingPlan.objects.get(plan_type=old_plan_type)
                    old_plan.is_active = False
                    old_plan.save()
                    self.stdout.write(f"Deactivated {old_plan.name} plan")
                except PricingPlan.DoesNotExist:
                    pass
            
            self.stdout.write(self.style.SUCCESS('Successfully migrated plans and subscriptions'))