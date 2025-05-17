from django.contrib import admin
from django import forms
from .models import Organization, PilotDefinition
from django.utils import timezone
from django.utils.html import format_html
from django.shortcuts import render
from django.urls import path
from django.contrib.admin.sites import AdminSite

original_index = admin.site.index
def custom_index(request, extra_context=None):
    extra_context = extra_context or {}
    
    # Add pending approvals count
    from apps.organizations.models import Organization
    extra_context['pending_approvals_count'] = Organization.objects.filter(
        approval_status='pending'
    ).count()
    
    return original_index(request, extra_context)

admin.site.index = custom_index

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

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('pending-approvals/', self.admin_site.admin_view(self.pending_approvals_view), name='pending_approvals'),
        ]
        return custom_urls + urls

    def pending_approvals_view(self, request):
        """Custom admin view to manage pending approvals"""
        # Get all organizations with pending approval status
        pending_orgs = Organization.objects.filter(approval_status='pending')
        
        # If approving or rejecting organizations
        if request.method == 'POST':
            action = request.POST.get('action')
            org_ids = request.POST.getlist('org_ids')
            
            # Handle single organization approval/rejection
            single_org_id = request.POST.get('single_org_id')
            if single_org_id and action:
                org_ids = [single_org_id]
            
            if org_ids and action:
                orgs = Organization.objects.filter(id__in=org_ids)
                
                if action == 'approve':
                    self.approve_organizations(request, orgs)
                elif action == 'reject':
                    self.reject_organizations(request, orgs)
            
            # Refresh the queryset after actions
            pending_orgs = Organization.objects.filter(approval_status='pending')
        
        context = {
            'title': 'Pending Organization Approvals',
            'pending_orgs': pending_orgs,
            'opts': self.model._meta,
            **self.admin_site.each_context(request),
        }
        return render(request, 'admin/organizations/pending_approvals.html', context)

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