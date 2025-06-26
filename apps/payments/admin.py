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
    EscrowPaymentLog,
    FreeAccountCode
)

# Import the new admin views
from . import views as payment_views

class CustomAdminMixin:
    """Mixin to add custom admin dashboard link and context"""
    change_list_template = 'admin/payments/change_list.html'
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['custom_dashboard_url'] = reverse('payments:admin_payment_dashboard')
        
        # Add payment stats for EscrowPayment model - Updated for 4-stage workflow
        if self.model._meta.model_name == 'escrowpayment':
            queryset = self.get_queryset(request)
            
            # 4-Stage Workflow Stats
            extra_context['invoice_pending_count'] = queryset.filter(status='pending').count()
            extra_context['invoice_sent_count'] = queryset.filter(status='instructions_sent').count()
            extra_context['payment_received_count'] = queryset.filter(
                status='received', pilot_bid__status='completed'
            ).count()
            extra_context['payment_released_count'] = queryset.filter(status='released').count()
            
            # Total escrow amount (payments in progress)
            extra_context['total_escrow_amount'] = queryset.filter(
                status__in=['received', 'instructions_sent']
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
        # Updated colors for 4-stage workflow
        colors = {
            'pending': '#3B82F6',           # Blue - Stage 1: Invoice Pending
            'instructions_sent': '#EAB308', # Yellow - Stage 2: Invoice Sent  
            'received': '#10B981',          # Green - Stage 3: Payment Received & Work Active
            'released': '#8B5CF6',          # Purple - Stage 4: Released to Startup
            'cancelled': '#EF4444'          # Red - Cancelled
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
        detail_url = reverse('payments:payment_holding_detail', args=[obj.id])
        return format_html(
            '<a href="{}" class="button" style="padding: 3px 8px;">View Details</a>',
            detail_url
        )
    actions_column.short_description = 'Actions'
    
    def status_timeline(self, obj):
        """Updated timeline for 4-stage workflow"""
        timeline_html = '<div style="margin: 10px 0;">'
        timeline_html += '<h3>4-Stage Workflow Timeline</h3>'
        
        # Stage 1: Created (Invoice Pending)
        if obj.created_at:
            timeline_html += self._timeline_entry(
                'Stage 1: Invoice Created', 
                obj.created_at, 
                '#3B82F6'
            )
        
        # Stage 2: Instructions Sent (Invoice Sent)
        if obj.instructions_sent_at:
            timeline_html += self._timeline_entry(
                'Stage 2: Invoice Sent to Enterprise', 
                obj.instructions_sent_at, 
                '#EAB308'
            )
        
        # Stage 3: Payment Received & Work Activated
        if obj.received_at:
            timeline_html += self._timeline_entry(
                'Stage 3: Payment Confirmed & Work Activated', 
                obj.received_at, 
                '#10B981'
            )
        
        # Stage 4: Payment Released
        if obj.released_at:
            timeline_html += self._timeline_entry(
                'Stage 4: Payment Released to Startup', 
                obj.released_at, 
                '#8B5CF6'
            )
        
        # Show current stage
        stage_info = self._get_current_stage_info(obj)
        timeline_html += f'<div style="margin-top: 15px; padding: 8px; background-color: #F3F4F6; border-radius: 5px;"><strong>Current Stage:</strong> {stage_info}</div>'
            
        timeline_html += '</div>'
        return mark_safe(timeline_html)
    status_timeline.short_description = '4-Stage Workflow Timeline'
    
    def _timeline_entry(self, label, timestamp, color):
        return f'''
        <div style="margin: 5px 0; padding: 8px; border-left: 4px solid {color}; background-color: #F9FAFB;">
            <strong style="color: {color};">{label}:</strong><br>
            <span style="color: #6B7280; font-size: 13px;">{timestamp.strftime("%B %d, %Y at %I:%M %p")}</span>
        </div>
        '''
    
    def _get_current_stage_info(self, obj):
        """Get current stage information for display"""
        stage_map = {
            'pending': 'Stage 1 of 4 - Invoice Pending',
            'instructions_sent': 'Stage 2 of 4 - Invoice Sent, Awaiting Payment',
            'received': 'Stage 3 of 4 - Payment Confirmed & Work Active',
            'released': 'Stage 4 of 4 - Payment Released (Complete)',
            'cancelled': 'Cancelled'
        }
        return stage_map.get(obj.status, 'Unknown Stage')
    
    def get_urls(self):
        """Add custom admin URLs for the 4-stage workflow"""
        urls = super().get_urls()
        custom_urls = [
            # Main payment dashboard
            path('dashboard/', 
                 self.admin_site.admin_view(payment_views.admin_payment_dashboard), 
                 name='payment_dashboard'),
            
            # Payment list and management
            path('payment-holding-services/', 
                 self.admin_site.admin_view(payment_views.admin_payment_holding_services), 
                 name='payment_holding_services'),
            
            # Individual payment management
            path('payment-holding/<int:payment_id>/', 
                 self.admin_site.admin_view(payment_views.admin_payment_holding_detail), 
                 name='payment_holding_detail'),
            
            # 4-Stage Workflow Actions
            # Stage 1→2: Mark invoice as sent
            path('bid/<int:bid_id>/mark-invoice-sent/', 
                 self.admin_site.admin_view(payment_views.admin_mark_invoice_sent), 
                 name='mark_invoice_sent'),
            
            # Stage 2→3: Confirm payment and activate work (combined)
            path('payment/<int:payment_id>/confirm-and-activate/', 
                 self.admin_site.admin_view(payment_views.admin_confirm_payment_and_activate), 
                 name='confirm_and_activate'),
            
            # Stage 3→4: Release payment to startup
            path('payment/<int:payment_id>/release-startup-payment/', 
                 self.admin_site.admin_view(payment_views.admin_release_startup_payment), 
                 name='release_startup_payment'),
            
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
    list_display = ('organization', 'plan', 'status', 'free_account_code', 'current_period_end')
    list_filter = ('status', 'plan', 'free_account_code__is_active')
    raw_id_fields = ('organization', 'free_account_code')
    
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

@admin.register(FreeAccountCode)
class FreeAccountCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'plan', 'description', 'free_months', 'times_used', 'max_uses', 'is_active', 'valid_until', 'created_at')
    list_filter = ('is_active', 'plan', 'free_months', 'valid_from', 'valid_until', 'created_at')
    search_fields = ('code', 'description', 'plan__name')
    readonly_fields = ('times_used', 'created_at', 'created_by')
    raw_id_fields = ('plan',)
    
    fieldsets = (
        ('Code Information', {
            'fields': ('code', 'description')
        }),
        ('Plan Settings', {
            'fields': ('plan', 'free_months')
        }),
        ('Validity Settings', {
            'fields': ('is_active', 'valid_from', 'valid_until', 'max_uses')
        }),
        ('Usage Tracking', {
            'fields': ('times_used', 'created_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by for new objects
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['deactivate_codes']
    
    def deactivate_codes(self, request, queryset):
        """Deactivate selected codes"""
        count = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {count} free account codes.")
    deactivate_codes.short_description = "Deactivate selected codes"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('generate-codes/', 
                 self.admin_site.admin_view(self.generate_codes_view), 
                 name='generate_free_codes'),
        ]
        return custom_urls + urls
    
    def generate_codes_view(self, request):
        """Custom view for generating multiple free account codes"""
        from django.shortcuts import render, redirect
        from django.contrib import messages
        from django.utils import timezone
        from datetime import timedelta
        
        if request.method == 'POST':
            try:
                count = int(request.POST.get('count', 1))
                plan_id = request.POST.get('plan_id')
                description = request.POST.get('description', '')
                valid_days = int(request.POST.get('valid_days', 365))
                free_months = int(request.POST.get('free_months', 12))
                max_uses = int(request.POST.get('max_uses', 1))
                
                # Validate inputs
                if count < 1 or count > 100:
                    messages.error(request, "Count must be between 1 and 100")
                    return render(request, 'admin/payments/generate_codes.html', {'plans': PricingPlan.objects.filter(is_active=True)})
                
                if not plan_id:
                    messages.error(request, "Please select a plan")
                    return render(request, 'admin/payments/generate_codes.html', {'plans': PricingPlan.objects.filter(is_active=True)})
                
                if valid_days < 1 or valid_days > 3650:  # Max 10 years
                    messages.error(request, "Valid days must be between 1 and 3650")
                    return render(request, 'admin/payments/generate_codes.html', {'plans': PricingPlan.objects.filter(is_active=True)})
                
                if free_months < 1 or free_months > 120:  # Max 10 years
                    messages.error(request, "Free months must be between 1 and 120")
                    return render(request, 'admin/payments/generate_codes.html', {'plans': PricingPlan.objects.filter(is_active=True)})
                
                if max_uses < 1 or max_uses > 1000:
                    messages.error(request, "Max uses must be between 1 and 1000")
                    return render(request, 'admin/payments/generate_codes.html', {'plans': PricingPlan.objects.filter(is_active=True)})
                
                # Get the selected plan
                try:
                    plan = PricingPlan.objects.get(id=plan_id)
                except PricingPlan.DoesNotExist:
                    messages.error(request, "Invalid plan selected")
                    return render(request, 'admin/payments/generate_codes.html', {'plans': PricingPlan.objects.filter(is_active=True)})
                
                # Generate codes
                generated_codes = []
                for i in range(count):
                    code_description = f"{description} ({i+1}/{count})" if count > 1 and description else description
                    code = FreeAccountCode.generate_code(
                        plan=plan,
                        description=code_description or f"Generated {timezone.now().strftime('%Y-%m-%d')}",
                        valid_days=valid_days,
                        max_uses=max_uses,
                        free_months=free_months,
                        created_by=request.user
                    )
                    generated_codes.append(code)
                
                messages.success(request, f"Successfully generated {count} free account codes!")
                
                # Store codes in session for display
                request.session['generated_codes'] = [
                    {
                        'code': code.code,
                        'plan_name': code.plan.name,
                        'description': code.description,
                        'valid_until': code.valid_until.strftime('%Y-%m-%d %H:%M'),
                        'free_months': code.free_months,
                        'max_uses': code.max_uses
                    }
                    for code in generated_codes
                ]
                
                return redirect('admin:payments_freeaccountcode_changelist')
                
            except ValueError as e:
                messages.error(request, f"Invalid input: {str(e)}")
            except Exception as e:
                messages.error(request, f"Error generating codes: {str(e)}")
        
        # GET request - show form with available plans
        plans = PricingPlan.objects.filter(is_active=True).order_by('plan_type', 'name')
        return render(request, 'admin/payments/generate_codes.html', {'plans': plans})
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        
        # Check if we have generated codes to display
        generated_codes = request.session.pop('generated_codes', None)
        if generated_codes:
            extra_context['generated_codes'] = generated_codes
        
        return super().changelist_view(request, extra_context)