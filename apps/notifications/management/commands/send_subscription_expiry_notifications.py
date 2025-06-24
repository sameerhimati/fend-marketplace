from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.payments.models import Subscription
from apps.notifications.services import create_notification


class Command(BaseCommand):
    help = 'Send subscription expiry notifications for subscriptions expiring in 7 days'

    def handle(self, *args, **options):
        # Calculate 7 days from now
        seven_days_from_now = timezone.now() + timedelta(days=7)
        
        # Find subscriptions expiring in 7 days (within 1 hour window for cron accuracy)
        expiring_subscriptions = Subscription.objects.filter(
            status='active',
            current_period_end__gte=seven_days_from_now,
            current_period_end__lt=seven_days_from_now + timedelta(hours=1),
            cancel_at_period_end=False  # Only for auto-renewing subscriptions having issues
        )
        
        count = 0
        for subscription in expiring_subscriptions:
            organization = subscription.organization
            
            # Notify all users in the organization
            for user in organization.users.all():
                create_notification(
                    recipient=user,
                    notification_type='subscription_expiring_soon',
                    title=f"⏰ Subscription Expiring Soon",
                    message=f"Your {subscription.plan.name} subscription expires in 7 days on {subscription.current_period_end.strftime('%B %d, %Y')}. Please ensure your payment method is up to date to avoid service interruption."
                )
                count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully sent {count} subscription expiry notifications'
            )
        )