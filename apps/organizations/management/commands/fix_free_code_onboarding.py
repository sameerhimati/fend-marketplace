from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.organizations.models import Organization
from apps.payments.models import Subscription


class Command(BaseCommand):
    help = 'Fix organizations with active free code subscriptions to mark them as onboarded'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find organizations with active free code subscriptions that aren't marked as onboarded
        organizations_to_fix = Organization.objects.filter(
            subscription__free_account_code__isnull=False,
            subscription__status='active',
            subscription__current_period_end__gt=timezone.now(),
            onboarding_completed=False
        ).select_related('subscription', 'subscription__plan', 'subscription__free_account_code')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN - Would update {organizations_to_fix.count()} organizations:')
            )
            for org in organizations_to_fix:
                subscription = org.subscription
                code = subscription.free_account_code
                self.stdout.write(
                    f"  • {org.name} ({org.type}) - Code: {code.code}, Plan: {subscription.plan.name}, Expires: {subscription.current_period_end.strftime('%Y-%m-%d')}"
                )
        else:
            count = 0
            for org in organizations_to_fix:
                org.onboarding_completed = True
                org.save()
                count += 1
                
                subscription = org.subscription
                code = subscription.free_account_code
                self.stdout.write(
                    f"✅ Updated: {org.name} ({org.type}) - Code: {code.code}, Plan: {subscription.plan.name}"
                )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully updated {count} organizations to be marked as onboarded'
                )
            )