from django.contrib import admin
from django import forms
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils import timezone
from django.contrib.admin.sites import AdminSite
from django.shortcuts import redirect
from .models import Organization, PilotDefinition, PartnerPromotion

# Import the new admin views
from . import views as org_views

class PilotDefinitionInline(admin.StackedInline):
    model = PilotDefinition
    can_delete = False
    verbose_name_plural = 'Pilot Definition'

class PartnerPromotionInline(admin.TabularInline):
    model = PartnerPromotion
    extra = 0
    max_num = 5
    fields = ('title', 'description', 'link_url', 'is_exclusive', 'is_active', 'is_featured', 'display_order')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('display_order', '-created_at')

# PartnerPromotion admin functionality is handled via inline in OrganizationAdmin
# Full admin interface can be added separately if needed

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'approval_status', 'featured_order', 'business_type', 'employee_count', 'founding_year', 'primary_contact_name', 'onboarding_completed', 'payment_status')
    list_filter = ('type', 'approval_status', 'business_type', 'employee_count', 'onboarding_completed', 'has_payment_method')
    list_editable = ('featured_order',)
    search_fields = ('name', 'primary_contact_name', 'users__email', 'website', 'headquarters_location')
    actions = ['approve_organizations', 'reject_organizations', 'set_as_featured', 'remove_from_featured']

    def payment_status(self, obj):
        if obj.onboarding_completed and obj.has_payment_method:
            return format_html('<span style="color: #10B981;">Paid ✓</span>')
        return format_html('<span style="color: #EF4444;">Unpaid</span>')
    payment_status.short_description = 'Payment'
    
    inlines = [PilotDefinitionInline, PartnerPromotionInline]

    fieldsets = [
        ('Basic Information', {
            'fields': ('name', 'type', 'website', 'description', 'logo', 'approval_status', 'approval_date')
        }),
        ('⭐ Featured Display Settings', {
            'fields': ('featured_order',),
            'description': 'Lower numbers appear first in featured sections (0 = highest priority, 999 = default). Use list view for bulk management.'
        }),
        ('Business Information', {
            'fields': (
                'business_type',
                'business_registration_number',
                'tax_identification_number'
            )
        }),
        ('Company Details', {
            'fields': (
                'employee_count',
                'founding_year', 
                'headquarters_location'
            ),
            'classes': ('collapse',),
        }),
        ('Social Media & Online Presence', {
            'fields': (
                'linkedin_url',
                'twitter_url',
            ),
            'classes': ('collapse',),
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
        }),
        ('Banking Information', {
            'fields': (
                'bank_name',
                'bank_account_number',
                'bank_routing_number'
            ),
            'classes': ('collapse',),
        })
    ]
    
    readonly_fields = ('approval_date',)

    class Media:
        js = ('admin/js/organization_type_toggle.js',)
        css = {
            'all': ('admin/css/organization_admin.css',)
        }

    def get_queryset(self, request):
        # Prefetch related users and promotions for performance
        return super().get_queryset(request).prefetch_related('users', 'partner_promotions')

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
    
    def set_as_featured(self, request, queryset):
        """Set selected organizations as featured (priority 0-10)"""
        next_order = 0
        for org in queryset:
            org.featured_order = next_order
            org.save()
            next_order += 1
        self.message_user(request, f'{queryset.count()} organizations set as featured with priority ordering.')
    set_as_featured.short_description = "Set as featured (highest priority)"

    def remove_from_featured(self, request, queryset):
        """Remove selected organizations from featured (set to 999)"""
        count = queryset.update(featured_order=999)
        self.message_user(request, f'{count} organizations removed from featured sections.')
    remove_from_featured.short_description = "Remove from featured"
    
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
        
        # Add featured content management info
        extra_context['featured_orgs_count'] = Organization.objects.filter(featured_order__lt=999).count()
        
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


@admin.register(PartnerPromotion)
class PartnerPromotionAdmin(admin.ModelAdmin):
    list_display = ('title', 'organization', 'is_exclusive', 'is_active', 'is_featured', 'display_order', 'created_at')
    list_filter = ('is_featured', 'is_exclusive', 'is_active', 'organization__type', 'created_at')
    search_fields = ('title', 'description', 'organization__name', 'link_url')
    list_editable = ('is_active', 'is_featured', 'display_order')
    actions = ['mark_as_featured', 'unmark_as_featured']
    ordering = ('organization', 'display_order', '-created_at')
    
    fieldsets = [
        (None, {
            'fields': ('organization', 'title', 'description', 'link_url')
        }),
        ('Settings', {
            'fields': ('is_exclusive', 'is_active', 'display_order')
        }),
        ('⭐ Featured Settings', {
            'fields': ('is_featured',),
            'description': 'Featured deals appear in hero sections (max 4 deals can be featured). Featured deals are ordered by recency.'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        })
    ]
    
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('organization')
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "organization":
            kwargs["queryset"] = Organization.objects.filter(
                approval_status='approved'
            ).order_by('name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def mark_as_featured(self, request, queryset):
        """Mark selected deals as featured (limit 4 total)"""
        # Check current featured count
        current_featured = PartnerPromotion.objects.filter(is_featured=True, is_active=True).count()
        selected_count = queryset.count()
        
        if current_featured + selected_count > 4:
            self.message_user(
                request, 
                f'Cannot feature {selected_count} deals. Only {4 - current_featured} slots available (current: {current_featured}/4).', 
                level='ERROR'
            )
            return
        
        try:
            count = queryset.update(is_featured=True)
            self.message_user(request, f'{count} deals marked as featured.')
        except Exception as e:
            self.message_user(request, f'Error: {str(e)}', level='ERROR')
    mark_as_featured.short_description = "Mark as featured"

    def unmark_as_featured(self, request, queryset):
        """Remove selected deals from featured"""
        count = queryset.update(is_featured=False)
        self.message_user(request, f'{count} deals removed from featured sections.')
    unmark_as_featured.short_description = "Remove from featured"
    
    def changelist_view(self, request, extra_context=None):
        """Add featured deals stats to the changelist view"""
        extra_context = extra_context or {}
        
        # Add featured content management info
        featured_count = PartnerPromotion.objects.filter(is_featured=True, is_active=True).count()
        extra_context['featured_deals_count'] = featured_count
        extra_context['featured_deals_remaining'] = 4 - featured_count
        
        return super().changelist_view(request, extra_context=extra_context)


# Keep the existing PilotDefinition admin registration if it exists separately
@admin.register(PilotDefinition)
class PilotDefinitionAdmin(admin.ModelAdmin):
    list_display = ('organization', 'is_private', 'created_at', 'updated_at')
    list_filter = ('is_private', 'organization__type', 'created_at')
    search_fields = ('organization__name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('organization')