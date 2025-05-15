from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import redirect
from .models import (
    PricingPlan, 
    Subscription, 
    Payment,
    EscrowPayment,
    EscrowPaymentLog
)

class CustomAdminMixin:
    """Mixin to add custom admin dashboard link"""
    change_list_template = 'admin/payments/change_list.html'
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['custom_dashboard_url'] = reverse('payments:admin_payment_dashboard')
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
            'pending': 'yellow',
            'instructions_sent': 'blue',
            'payment_initiated': 'indigo',
            'received': 'green',
            'released': 'purple',
            'cancelled': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="display: inline-block; padding: 3px 10px; '
            'background-color: {}; color: white; border-radius: 15px; '
            'font-size: 11px; font-weight: bold;">{}</span>',
            f'#{color}' if color != 'yellow' else '#EAB308',
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
            timeline_html += self._timeline_entry('Created', obj.created_at, 'green')
        if obj.instructions_sent_at:
            timeline_html += self._timeline_entry('Instructions Sent', obj.instructions_sent_at, 'blue')
        if obj.payment_initiated_at:
            timeline_html += self._timeline_entry('Payment Initiated', obj.payment_initiated_at, 'indigo')
        if obj.received_at:
            timeline_html += self._timeline_entry('Payment Received', obj.received_at, 'green')
        if obj.released_at:
            timeline_html += self._timeline_entry('Payment Released', obj.released_at, 'purple')
            
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
        urls = super().get_urls()
        from django.urls import path
        custom_urls = [
            path('dashboard/', self.admin_site.admin_view(self.dashboard_view), 
                 name='payments_escrowpayment_dashboard'),
        ]
        return custom_urls + urls
    
    def dashboard_view(self, request):
        return redirect('payments:admin_payment_dashboard')

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

# Update other model admins with the mixin
@admin.register(PricingPlan)
class PricingPlanAdmin(CustomAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'plan_type', 'price', 'billing_frequency', 'pilot_limit', 'is_active')
    list_filter = ('plan_type', 'billing_frequency', 'is_active')

@admin.register(Subscription)
class SubscriptionAdmin(CustomAdminMixin, admin.ModelAdmin):
    list_display = ('organization', 'plan', 'status', 'current_period_end')
    list_filter = ('status', 'plan')
    raw_id_fields = ('organization',)

@admin.register(Payment)
class PaymentAdmin(CustomAdminMixin, admin.ModelAdmin):
    list_display = ('organization', 'payment_type', 'amount', 'status', 'created_at')
    list_filter = ('payment_type', 'status', 'created_at')
    raw_id_fields = ('organization', 'subscription')