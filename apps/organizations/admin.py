from django.contrib import admin
from django import forms
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils import timezone
from django.contrib.admin.sites import AdminSite
from django.shortcuts import redirect
from .models import Organization, PilotDefinition

# Import the new admin views
from . import views as org_views

class PilotDefinitionInline(admin.StackedInline):
    model = PilotDefinition
    can_delete = False
    verbose_name_plural = 'Pilot Definition'

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'approval_status', 'business_type', 'primary_contact_name', 'onboarding_completed', 'payment_status')
    list_filter = ('type', 'approval_status', 'business_type', 'onboarding_completed', 'has_payment_method')
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
        """Bulk action to approve selected organizations"""
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
    approve_organizations.short_description = "Approve selected organizations"
    
    def reject_organizations(self, request, queryset):
        """Bulk action to reject selected organizations"""
        count = queryset.update(approval_status='rejected')
        self.message_user(request, f'{count} organizations were rejected.')
    reject_organizations.short_description = "Reject selected organizations"

    def get_urls(self):
        """Add custom admin URLs for the enhanced workflow"""
        urls = super().get_urls()
        custom_urls = [
            # Main approval dashboard
            path('pending-approvals/', 
                 self.admin_site.admin_view(org_views.admin_pending_approvals), 
                 name='pending_approvals'),
            
            # Individual organization review
            path('organization/<int:org_id>/', 
                 self.admin_site.admin_view(org_views.admin_organization_detail), 
                 name='organization_detail'),
            
            # Organization approval actions
            path('organization/<int:org_id>/approve/', 
                 self.admin_site.admin_view(org_views.admin_approve_organization), 
                 name='approve_organization'),
            
            path('organization/<int:org_id>/reject/', 
                 self.admin_site.admin_view(org_views.admin_reject_organization), 
                 name='reject_organization'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        """Add statistics to the changelist view"""
        extra_context = extra_context or {}
        
        # Add pending approvals count for the admin dashboard
        extra_context['pending_approvals_count'] = Organization.objects.filter(
            approval_status='pending'
        ).count()
        
        # Add other useful stats
        extra_context['total_organizations'] = Organization.objects.count()
        extra_context['enterprise_count'] = Organization.objects.filter(type='enterprise').count()
        extra_context['startup_count'] = Organization.objects.filter(type='startup').count()
        
        return super().changelist_view(request, extra_context=extra_context)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        # Add custom help text or validation if needed
        if 'pilot_definition-0-description' in form.base_fields:
            form.base_fields['pilot_definition-0-description'] = forms.CharField(
                widget=forms.Textarea,
                required=False,
                help_text="Provide a detailed description of the pilot"
            )
        
        return form