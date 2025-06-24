from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.organizations.models import PartnerPromotion
from apps.notifications.services import create_notification


class Command(BaseCommand):
    help = 'Send deal refresh notifications for promotions that are 30 days old'

    def handle(self, *args, **options):
        # Calculate 30 days ago
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Find active promotions that haven't been updated in 30 days
        stale_promotions = PartnerPromotion.objects.filter(
            is_active=True,
            updated_at__lte=thirty_days_ago
        )
        
        count = 0
        for promotion in stale_promotions:
            organization = promotion.organization
            
            # Notify all users in the organization that created the promotion
            for user in organization.users.all():
                create_notification(
                    recipient=user,
                    notification_type='deal_expiring_soon',
                    title=f"📅 Time to Refresh Deal: {promotion.title}",
                    message=f"Your promotion '{promotion.title}' was created {promotion.created_at.strftime('%B %d, %Y')}. Consider updating it with fresh content to keep it engaging for partners."
                )
                count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully sent {count} deal refresh notifications'
            )
        )