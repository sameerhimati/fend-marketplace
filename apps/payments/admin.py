from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db.models import Sum, Count
from django.shortcuts import redirect
from .models import (
    PricingPlan, 
    Subscription, 
    Payment,
    EscrowPayment,
    EscrowPaymentLog
)

# Import the new admin views
from . import views as payment_views

class CustomAdminMixin:
    """Mixin to add custom admin dashboard link and context"""
    change_list_template = 'admin/payments/change_list.html'
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['custom_dashboard_url'] = reverse('payments:admin_payment_dashboard')
        
        # Add payment stats for EscrowPayment model
        if self.model._meta.model_name == 'escrowpayment':
            queryset = self.get_queryset(request)
            extra_context['payment_initiated_count'] = queryset.filter(status='payment_initiated').count()
            extra_context['payment_received_count'] = queryset.filter(
                status='received', pilot_bid__status='completed'
            ).count()
            extra_context['payment_released_count'] = queryset.filter(status='released').count()
            extra_context['total_escrow_amount'] = queryset.filter(
                status__in=['received', 'payment_initiated']
            ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        return super().changelist_view(request, extra_context=extra_context)

@admin.register(EscrowPayment)
class EscrowPaymentAdmin(CustomAdminMixin, admin.ModelAdmin):
    list_display = ('reference_code', 'pilot_bid_link', 'total_amount', 'startup_amount', 
                   'status_badge', 'created_at', 'actions_column')
    list_filter = ('status', 'created_at')
    search_fields = ('reference_code', 'pilot_bid__pilot__title')
    raw_id_fields = ('pilot_bid',)
    readonly_fields = ('created_at', 'reference_code', 'status_timeline')
    
    def pilot_bid_link(self, obj):
        url = reverse('admin:pilots_pilotbid_change', args=[obj.pilot_bid.id])
        return format_html('<a href="{}">{}</a>', url, obj.pilot_bid)
    pilot_bid_link.short_description = 'Pilot Bid'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#EAB308',
            'instructions_sent': '#3B82F6',
            'payment_initiated': '#6366F1',
            'received': '#10B981',
            'released': '#8B5CF6',
            'cancelled': '#EF4444'
        }
        color = colors.get(obj.status, '#6B7280')
        return format_html(
            '<span style="display: inline-block; padding: 3px 10px; '
            'background-color: {}; color: white; border-radius: 15px; '
            'font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def actions_column(self, obj):
        detail_url = reverse('payments:admin_escrow_payment_detail', args=[obj.id])
        return format_html(
            '<a href="{}" class="button" style="padding: 3px 8px;">View Details</a>',
            detail_url
        )
    actions_column.short_description = 'Actions'
    
    def status_timeline(self, obj):
        timeline_html = '<div style="margin: 10px 0;">'
        timeline_html += '<h3>Status Timeline</h3>'
        
        # Add timeline entries
        if obj.created_at:
            timeline_html += self._timeline_entry('Created', obj.created_at, '#10B981')
        if obj.instructions_sent_at:
            timeline_html += self._timeline_entry('Instructions Sent', obj.instructions_sent_at, '#3B82F6')
        if obj.payment_initiated_at:
            timeline_html += self._timeline_entry('Payment Initiated', obj.payment_initiated_at, '#6366F1')
        if obj.received_at:
            timeline_html += self._timeline_entry('Payment Received', obj.received_at, '#10B981')
        if obj.released_at:
            timeline_html += self._timeline_entry('Payment Released', obj.released_at, '#8B5CF6')
            
        timeline_html += '</div>'
        return mark_safe(timeline_html)
    status_timeline.short_description = 'Status Timeline'
    
    def _timeline_entry(self, label, timestamp, color):
        return f'''
        <div style="margin: 5px 0; padding: 5px; border-left: 3px solid {color};">
            <strong>{label}:</strong> {timestamp.strftime("%B %d, %Y at %I:%M %p")}
        </div>
        '''
    
    def get_urls(self):
        """Add custom admin URLs for the enhanced workflow"""
        urls = super().get_urls()
        custom_urls = [
            # Main payment dashboard
            path('dashboard/', 
                 self.admin_site.admin_view(payment_views.admin_payment_dashboard), 
                 name='payment_dashboard'),
            
            # Payment list and management
            path('escrow-payments/', 
                 self.admin_site.admin_view(payment_views.admin_escrow_payments), 
                 name='escrow_payments'),
            
            # Individual payment management
            path('escrow-payment/<int:payment_id>/', 
                 self.admin_site.admin_view(payment_views.admin_escrow_payment_detail), 
                 name='escrow_payment_detail'),
            
            # Payment workflow actions
            path('escrow-payment/<int:payment_id>/received/', 
                 self.admin_site.admin_view(payment_views.admin_mark_payment_received), 
                 name='mark_payment_received'),
            
            path('escrow-payment/<int:payment_id>/release/', 
                 self.admin_site.admin_view(payment_views.admin_release_payment), 
                 name='release_payment'),
            
            path('escrow-payment/<int:payment_id>/kickoff/', 
                 self.admin_site.admin_view(payment_views.admin_kickoff_pilot), 
                 name='kickoff_pilot'),
            
            # Utilities
            path('export-csv/', 
                 self.admin_site.admin_view(payment_views.admin_export_payments_csv), 
                 name='export_payments_csv'),
        ]
        return custom_urls + urls

@admin.register(EscrowPaymentLog)
class EscrowPaymentLogAdmin(admin.ModelAdmin):
    list_display = ('escrow_payment', 'status_change', 'changed_by', 'created_at')
    list_filter = ('new_status', 'created_at')
    search_fields = ('escrow_payment__reference_code', 'notes')
    raw_id_fields = ('escrow_payment', 'changed_by')
    readonly_fields = ('created_at',)
    
    def status_change(self, obj):
        if obj.previous_status:
            return f"{obj.previous_status} → {obj.new_status}"
        return f"Created as {obj.new_status}"
    status_change.short_description = 'Status Change'

@admin.register(PricingPlan)
class PricingPlanAdmin(CustomAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'plan_type', 'price', 'billing_frequency', 'pilot_limit', 'is_active')
    list_filter = ('plan_type', 'billing_frequency', 'is_active')
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['custom_dashboard_url'] = reverse('payments:admin_payment_dashboard')
        return super().changelist_view(request, extra_context=extra_context)

@admin.register(Subscription)
class SubscriptionAdmin(CustomAdminMixin, admin.ModelAdmin):
    list_display = ('organization', 'plan', 'status', 'current_period_end')
    list_filter = ('status', 'plan')
    raw_id_fields = ('organization',)
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['custom_dashboard_url'] = reverse('payments:admin_payment_dashboard')
        return super().changelist_view(request, extra_context=extra_context)

@admin.register(Payment)
class PaymentAdmin(CustomAdminMixin, admin.ModelAdmin):
    list_display = ('organization', 'payment_type', 'amount', 'status', 'created_at')
    list_filter = ('payment_type', 'status', 'created_at')
    raw_id_fields = ('organization', 'subscription')
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['custom_dashboard_url'] = reverse('payments:admin_payment_dashboard')
        return super().changelist_view(request, extra_context=extra_context)