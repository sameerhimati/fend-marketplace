from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.organizations.models import Organization, PartnerPromotion
from apps.notifications.services import create_notification


class Command(BaseCommand):
    help = 'Send monthly deals digest to all active organizations'

    def handle(self, *args, **options):
        # Get all active promotions
        active_promotions = PartnerPromotion.objects.filter(
            is_active=True
        ).select_related('organization').order_by('-created_at')
        
        if not active_promotions.exists():
            self.stdout.write(self.style.WARNING('No active promotions found'))
            return
        
        # Get all organizations with active subscriptions
        active_organizations = Organization.objects.filter(
            subscription__status='active'
        ).distinct()
        
        count = 0
        for organization in active_organizations:
            # Get promotions from other organizations (not their own)
            other_promotions = active_promotions.exclude(
                organization=organization
            )[:5]  # Limit to top 5 promotions
            
            if other_promotions.exists():
                # Create digest message
                promotion_list = []
                for i, promo in enumerate(other_promotions, 1):
                    promotion_list.append(f"{i}. {promo.title} by {promo.organization.name}")
                
                promotions_text = "\n".join(promotion_list)
                
                # Notify all users in the organization
                for user in organization.users.all():
                    create_notification(
                        recipient=user,
                        notification_type='monthly_deals_digest',
                        title=f"🎉 Monthly Partner Deals - {timezone.now().strftime('%B %Y')}",
                        message=f"Check out this month's top partner deals:\n\n{promotions_text}\n\nView all deals in your dashboard to explore partnership opportunities!"
                    )
                    count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully sent {count} monthly deals digest notifications to {active_organizations.count()} organizations'
            )
        )