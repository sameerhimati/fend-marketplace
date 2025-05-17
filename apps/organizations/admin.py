from django.contrib import admin
from django import forms
from .models import Organization, PilotDefinition
from django.utils import timezone
from django.utils.html import format_html

class PilotDefinitionInline(admin.StackedInline):
    model = PilotDefinition
    can_delete = False
    verbose_name_plural = 'Pilot Definition'

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'approval_status', 'business_type', 'primary_contact_name', 'onboarding_completed')
    list_filter = ('type', 'approval_status', 'business_type', 'onboarding_completed')
    search_fields = ('name', 'primary_contact_name', 'users__email')
    actions = ['approve_organizations', 'reject_organizations']

    def payment_status(self, obj):
        if obj.onboarding_completed and obj.has_payment_method:
            return format_html('<span style="color: #10B981;">Paid ✓</span>')
        return format_html('<span style="color: #EF4444;">Unpaid</span>')
    payment_status.short_description = 'Payment'
    
    inlines = [PilotDefinitionInline]

    fieldsets = [
        ('Basic Information', {
            'fields': ('name', 'type', 'website', 'approval_status', 'approval_date')
        }),
        ('Business Information', {
            'fields': (
                'business_type',
                'business_registration_number',
                'tax_identification_number'
            )
        }),
        ('Primary Contact', {
            'fields': (
                'primary_contact_name',
                'country_code',
                'primary_contact_phone'
            )
        }),
        ('Status', {
            'fields': ('onboarding_completed',)
        }),
        ('Payment Information', {
            'fields': ('stripe_customer_id', 'has_payment_method')
        })
    ]
    
    readonly_fields = ('approval_date',)

    class Media:
        js = ('admin/js/organization_type_toggle.js',)
        css = {
            'all': ('admin/css/organization_admin.css',)
        }

    def get_queryset(self, request):
        # Prefetch related users for performance
        return super().get_queryset(request).prefetch_related('users')

    def approve_organizations(self, request, queryset):
        """Action to approve the selected organizations"""
        from django.utils import timezone
        from apps.notifications.services import create_notification
        
        for org in queryset:
            org.approval_status = 'approved'
            org.approval_date = timezone.now()
            org.save()
            
            # Create in-app notification for all organization users
            for user in org.users.all():
                create_notification(
                    recipient=user,
                    notification_type='account_approved',
                    title="Account Approved!",
                    message=f"Your {org.get_type_display()} account has been approved. You now have full access to Fend Marketplace."
                )
        
        self.message_user(request, f'{queryset.count()} organizations were approved.')
    
    def reject_organizations(self, request, queryset):
        """Action to reject the selected organizations"""
        count = queryset.update(
            approval_status='rejected'
        )
        self.message_user(request, f'{count} organizations were rejected.')
    reject_organizations.short_description = "Reject selected organizations"

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        # Add a description field to the PilotDefinition
        if 'pilot_definition-0-performance_metrics' in form.base_fields:
            form.base_fields['pilot_definition-0-description'] = forms.CharField(
                widget=forms.Textarea,
                required=False,
                help_text="Provide a detailed description of the pilot"
            )
        
        return form