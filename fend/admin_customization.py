"""
Centralized admin index customization to avoid circular imports and recursion.
This file should be imported in fend/settings/base.py or fend/__init__.py
"""
from django.contrib import admin
from django.db.models import Sum


def get_admin_statistics():
    """
    Centralized function to gather all admin statistics.
    This prevents circular dependencies and recursion issues.
    """
    stats = {
        # Default values in case of errors
        'pending_approvals_count': 0,
        'total_organizations': 0,
        'enterprise_count': 0,
        'startup_count': 0,
        'pilot_count_pending': 0,
        'total_pilots': 0,
        'active_pilots_count': 0,
        'published_pilots_count': 0,
        'total_bids': 0,
        'active_bids': 0,
        'payment_stats': {
            'pending_count': 0,
            'verification_count': 0,
            'release_count': 0,
            'activation_count': 0,
            'total_payment_holding_value': 0,
            'monthly_revenue': 0,
        }
    }
    
    try:
        # Import models here to avoid circular imports
        from apps.organizations.models import Organization
        from apps.pilots.models import Pilot, PilotBid
        from apps.payments.models import PaymentHoldingService
        
        # Organization statistics
        stats['pending_approvals_count'] = Organization.objects.filter(
            approval_status='pending'
        ).count()
        stats['total_organizations'] = Organization.objects.count()
        stats['enterprise_count'] = Organization.objects.filter(type='enterprise').count()
        stats['startup_count'] = Organization.objects.filter(type='startup').count()
        
        # Pilot statistics
        stats['pilot_count_pending'] = Pilot.objects.filter(
            status='pending_approval', verified=False
        ).count()
        stats['total_pilots'] = Pilot.objects.count()
        stats['active_pilots_count'] = Pilot.objects.filter(
            status__in=['published', 'in_progress']
        ).count()
        stats['published_pilots_count'] = Pilot.objects.filter(
            status='published'
        ).count()
        
        # Bid statistics
        stats['total_bids'] = PilotBid.objects.count()
        stats['active_bids'] = PilotBid.objects.filter(
            status__in=['pending', 'under_review', 'approved', 'live']
        ).count()
        
        # Payment statistics
        needs_verification = PaymentHoldingService.objects.filter(status='payment_initiated').count()
        ready_for_release = PaymentHoldingService.objects.filter(
            status='received', pilot_bid__status='completed'
        ).count()
        payment_received_pilots = PaymentHoldingService.objects.filter(
            status='received', pilot_bid__status='approval_pending'
        ).count()
        total_payment_holding_amount = PaymentHoldingService.objects.filter(
            status__in=['received', 'payment_initiated']
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        stats['payment_stats'] = {
            'pending_count': needs_verification + payment_received_pilots,
            'verification_count': needs_verification,
            'release_count': ready_for_release,
            'activation_count': payment_received_pilots,
            'total_payment_holding_value': total_payment_holding_amount,
            'monthly_revenue': 0,  # Calculate based on your needs
        }
        
    except Exception as e:
        # If there are any database issues, just use default values
        # This prevents the admin from crashing
        print(f"Error gathering admin statistics: {e}")
    
    return stats


def custom_admin_index(request, extra_context=None):
    """
    Enhanced admin index with comprehensive statistics.
    This replaces all the individual admin index overrides.
    """
    from django.contrib.admin.sites import site
    
    extra_context = extra_context or {}
    
    # Get all statistics from our centralized function
    stats = get_admin_statistics()
    
    # Add all statistics to the context
    extra_context.update(stats)
    
    # Call the original Django admin index
    return site.each_context(request)


def initialize_admin_customization():
    """
    Initialize the admin customization.
    Call this function once during Django startup.
    """
    # Store the original index function
    original_index = admin.site.index
    
    def enhanced_index(request, extra_context=None):
        # Get statistics
        stats = get_admin_statistics()
        
        # Merge with any existing extra_context
        if extra_context is None:
            extra_context = {}
        extra_context.update(stats)
        
        # Call the original index with enhanced context
        return original_index(request, extra_context)
    
    # Override the admin site index with our enhanced version
    admin.site.index = enhanced_index