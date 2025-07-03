from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from apps.payments.models import PaymentHoldingService, Subscription
from apps.pilots.models import PilotBid

def stripe_key(request):
    return {
        'STRIPE_PUBLISHABLE_KEY': settings.STRIPE_PUBLISHABLE_KEY
    }

def payment_stats(request):
    """Add payment statistics to context"""
    if request.user.is_staff:
        start_of_month = timezone.now().replace(day=1, hour=0, minute=0, second=0)
        
        pending_count = PaymentHoldingService.objects.filter(status='payment_initiated').count()
        ready_count = PaymentHoldingService.objects.filter(
            status='received',
            pilot_bid__status='completed'
        ).count()
        
        total_payment_holding = PaymentHoldingService.objects.filter(
            status__in=['payment_initiated', 'received']
        ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        released_month = PaymentHoldingService.objects.filter(
            status='released',
            released_at__gte=start_of_month
        ).aggregate(Sum('startup_amount'))['startup_amount__sum'] or 0
        
        released_count_month = PaymentHoldingService.objects.filter(
            status='released',
            released_at__gte=start_of_month
        ).count()
        
        # Add active pilots count for navigation
        active_pilots_count = PilotBid.objects.filter(status='live').count()
        
        return {
            'payment_stats': {
                'pending_count': pending_count,
                'ready_count': ready_count,
                'total_payment_holding': f"{total_payment_holding:,.0f}",
                'released_month': f"{released_month:,.0f}",
                'released_count_month': released_count_month,
            },
            'active_pilots_count': active_pilots_count,
        }
    return {}

def subscription_warnings(request):
    """
    Add subscription warning context - ONLY for actual payment issues
    """
    if not request.user.is_authenticated:
        return {}
    
    organization = getattr(request.user, 'organization', None)
    if not organization:
        return {}
    
    # Check if user dismissed warning for this session
    session_key = f'dismissed_subscription_warning_{organization.id}'
    if request.session.get(session_key):
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
        has_payment_method = organization.has_payment_method
        
        # SMART LOGIC: Only warn if there's actually a payment issue
        should_warn = False
        warning_reason = None
        
        if is_free_trial:
            # Free trial users always need to add payment method
            should_warn = True
            warning_reason = "free_trial_ending"
        elif not has_payment_method:
            # Paid users without payment method
            should_warn = True  
            warning_reason = "no_payment_method"
        elif subscription.status in ['past_due', 'incomplete', 'incomplete_expired']:
            # Payment issues with existing method
            should_warn = True
            warning_reason = "payment_failed"
        else:
            # Has payment method and subscription is healthy - no warning needed
            should_warn = False
        
        if not should_warn:
            return {}
        
        # Generate appropriate warning based on urgency and reason
        warning_data = None
        
        if days_until_expiry <= 1:
            if warning_reason == "free_trial_ending":
                warning_data = {
                    'level': 'danger',
                    'urgency': 'critical', 
                    'message': f'Your free trial expires {"today" if days_until_expiry == 0 else "tomorrow"}!',
                    'action': 'Add payment method now',
                    'days_left': days_until_expiry,
                    'is_free_trial': True,
                    'reason': warning_reason
                }
            else:
                warning_data = {
                    'level': 'danger',
                    'urgency': 'critical',
                    'message': f'Payment issue - subscription expires {"today" if days_until_expiry == 0 else "tomorrow"}!',
                    'action': 'Fix payment method now',
                    'days_left': days_until_expiry, 
                    'is_free_trial': False,
                    'reason': warning_reason
                }
        elif days_until_expiry <= 7:
            if warning_reason == "free_trial_ending":
                warning_data = {
                    'level': 'warning',
                    'urgency': 'high',
                    'message': f'Your free trial expires in {days_until_expiry} day{"s" if days_until_expiry != 1 else ""}',
                    'action': 'Add payment method',
                    'days_left': days_until_expiry,
                    'is_free_trial': True,
                    'reason': warning_reason
                }
            else:
                warning_data = {
                    'level': 'warning', 
                    'urgency': 'high',
                    'message': f'Payment issue - subscription expires in {days_until_expiry} day{"s" if days_until_expiry != 1 else ""}',
                    'action': 'Update payment method',
                    'days_left': days_until_expiry,
                    'is_free_trial': False,
                    'reason': warning_reason
                }
        elif days_until_expiry <= 14 and warning_reason == "free_trial_ending":
            warning_data = {
                'level': 'info',
                'urgency': 'medium',
                'message': f'Your free trial expires in {days_until_expiry} days',
                'action': 'Setup payment method',
                'days_left': days_until_expiry,
                'is_free_trial': True,
                'reason': warning_reason
            }
        elif days_until_expiry <= 30 and warning_reason == "free_trial_ending":
            warning_data = {
                'level': 'info',
                'urgency': 'low', 
                'message': f'Your free trial expires in {days_until_expiry} days',
                'action': 'Consider setting up payment',
                'days_left': days_until_expiry,
                'is_free_trial': True,
                'reason': warning_reason
            }
        
        return {
            'subscription_warning': warning_data
        }
        
    except Subscription.DoesNotExist:
        return {}