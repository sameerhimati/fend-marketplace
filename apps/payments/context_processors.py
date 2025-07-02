from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from apps.payments.models import EscrowPayment, Subscription
from apps.pilots.models import PilotBid

def stripe_key(request):
    return {
        'STRIPE_PUBLISHABLE_KEY': settings.STRIPE_PUBLISHABLE_KEY
    }

def payment_stats(request):
    """Add payment statistics to context"""
    if request.user.is_staff:
        start_of_month = timezone.now().replace(day=1, hour=0, minute=0, second=0)
        
        pending_count = EscrowPayment.objects.filter(status='payment_initiated').count()
        ready_count = EscrowPayment.objects.filter(
            status='received',
            pilot_bid__status='completed'
        ).count()
        
        total_escrow = EscrowPayment.objects.filter(
            status__in=['payment_initiated', 'received']
        ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        released_month = EscrowPayment.objects.filter(
            status='released',
            released_at__gte=start_of_month
        ).aggregate(Sum('startup_amount'))['startup_amount__sum'] or 0
        
        released_count_month = EscrowPayment.objects.filter(
            status='released',
            released_at__gte=start_of_month
        ).count()
        
        # Add active pilots count for navigation
        active_pilots_count = PilotBid.objects.filter(status='live').count()
        
        return {
            'payment_stats': {
                'pending_count': pending_count,
                'ready_count': ready_count,
                'total_escrow': f"{total_escrow:,.0f}",
                'released_month': f"{released_month:,.0f}",
                'released_count_month': released_count_month,
            },
            'active_pilots_count': active_pilots_count,
        }
    return {}

def subscription_warnings(request):
    """
    Add subscription warning context to all templates
    """
    if not request.user.is_authenticated:
        return {}
    
    organization = getattr(request.user, 'organization', None)
    if not organization:
        return {}
    
    try:
        subscription = organization.subscription
        if not subscription or subscription.status != 'active':
            return {}
        
        now = timezone.now()
        days_until_expiry = (subscription.current_period_end - now).days
        
        # Only show warnings if subscription expires within 30 days
        if days_until_expiry > 30:
            return {}
        
        is_free_trial = subscription.free_account_code is not None
        
        # Determine warning level and message
        warning_data = None
        if days_until_expiry <= 1:
            warning_data = {
                'level': 'danger',
                'urgency': 'critical',
                'message': f'Your {"free trial" if is_free_trial else "subscription"} expires {"today" if days_until_expiry == 0 else "tomorrow"}!',
                'action': 'Add payment method now' if is_free_trial else 'Update payment method',
                'days_left': days_until_expiry,
                'is_free_trial': is_free_trial
            }
        elif days_until_expiry <= 7:
            warning_data = {
                'level': 'warning',
                'urgency': 'high',
                'message': f'Your {"free trial" if is_free_trial else "subscription"} expires in {days_until_expiry} day{"s" if days_until_expiry != 1 else ""}',
                'action': 'Add payment method' if is_free_trial else 'Verify payment method',
                'days_left': days_until_expiry,
                'is_free_trial': is_free_trial
            }
        elif days_until_expiry <= 14:
            warning_data = {
                'level': 'info',
                'urgency': 'medium',
                'message': f'Your {"free trial" if is_free_trial else "subscription"} expires in {days_until_expiry} days',
                'action': 'Setup payment method' if is_free_trial else 'Check payment method',
                'days_left': days_until_expiry,
                'is_free_trial': is_free_trial
            }
        elif days_until_expiry <= 30:
            warning_data = {
                'level': 'info',
                'urgency': 'low',
                'message': f'Your {"free trial" if is_free_trial else "subscription"} expires in {days_until_expiry} days',
                'action': 'Consider setting up payment' if is_free_trial else 'Review subscription',
                'days_left': days_until_expiry,
                'is_free_trial': is_free_trial
            }
        
        return {
            'subscription_warning': warning_data
        }
        
    except Subscription.DoesNotExist:
        return {}