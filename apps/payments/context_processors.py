from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from apps.payments.models import EscrowPayment

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
        
        return {
            'payment_stats': {
                'pending_count': pending_count,
                'ready_count': ready_count,
                'total_escrow': f"{total_escrow:,.0f}",
                'released_month': f"{released_month:,.0f}",
                'released_count_month': released_count_month,
            }
        }
    return {}