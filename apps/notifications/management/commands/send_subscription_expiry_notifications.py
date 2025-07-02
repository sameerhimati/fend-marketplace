from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.payments.models import Subscription
from apps.notifications.services import create_notification


class Command(BaseCommand):
    help = 'Send subscription expiry notifications for subscriptions expiring in 30, 14, 7, or 1 day(s)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            choices=[30, 14, 7, 1],
            help='Number of days before expiry to send notifications (default: 7)'
        )

    def handle(self, *args, **options):
        days_ahead = options['days']
        target_date = timezone.now() + timedelta(days=days_ahead)
        
        # Find subscriptions expiring in X days (within 1 hour window for cron accuracy)
        expiring_subscriptions = Subscription.objects.filter(
            status='active',
            current_period_end__gte=target_date,
            current_period_end__lt=target_date + timedelta(hours=1)
        ).select_related('organization', 'plan', 'free_account_code')
        
        count = 0
        for subscription in expiring_subscriptions:
            organization = subscription.organization
            is_free_code = subscription.free_account_code is not None
            
            # Different messaging for free code vs paid subscriptions
            if is_free_code:
                if days_ahead == 30:
                    title = "🎯 Free Trial Ending Soon"
                    message = f"Your free {subscription.plan.name} trial expires in 30 days on {subscription.current_period_end.strftime('%B %d, %Y')}. Add a payment method now to continue your subscription seamlessly."
                elif days_ahead == 14:
                    title = "⚠️ Free Trial Expires in 2 Weeks"
                    message = f"Your free {subscription.plan.name} trial expires in 14 days on {subscription.current_period_end.strftime('%B %d, %Y')}. Don't lose access - add your payment method today!"
                elif days_ahead == 7:
                    title = "🚨 Free Trial Expires in 1 Week"
                    message = f"Your free {subscription.plan.name} trial expires in 7 days on {subscription.current_period_end.strftime('%B %d, %Y')}. Add a payment method now to avoid losing access to the platform."
                else:  # 1 day
                    title = "🔥 Free Trial Expires Tomorrow!"
                    message = f"Your free {subscription.plan.name} trial expires tomorrow on {subscription.current_period_end.strftime('%B %d, %Y')}. Add your payment method immediately to maintain access."
            else:
                # Regular paid subscription warnings
                if days_ahead == 30:
                    title = "📋 Subscription Renewal in 30 Days"
                    message = f"Your {subscription.plan.name} subscription renews in 30 days on {subscription.current_period_end.strftime('%B %d, %Y')}. Please ensure your payment method is up to date."
                elif days_ahead == 14:
                    title = "💳 Payment Method Check"
                    message = f"Your {subscription.plan.name} subscription renews in 14 days on {subscription.current_period_end.strftime('%B %d, %Y')}. Please verify your payment method is current."
                elif days_ahead == 7:
                    title = "⏰ Subscription Expiring Soon"
                    message = f"Your {subscription.plan.name} subscription expires in 7 days on {subscription.current_period_end.strftime('%B %d, %Y')}. Please ensure your payment method is up to date to avoid service interruption."
                else:  # 1 day
                    title = "⚠️ Subscription Expires Tomorrow"
                    message = f"Your {subscription.plan.name} subscription expires tomorrow on {subscription.current_period_end.strftime('%B %d, %Y')}. Please update your payment method immediately."
            
            # Notify all users in the organization
            for user in organization.users.all():
                create_notification(
                    recipient=user,
                    notification_type='subscription_expiring_soon',
                    title=title,
                    message=message
                )
                count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully sent {count} subscription expiry notifications for {days_ahead} day(s) ahead'
            )
        )