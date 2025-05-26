from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django import forms
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils import timezone
from django.http import HttpResponseRedirect
from django.contrib import messages
from .models import Pilot, PilotBid

# Import the new admin views
from . import views as pilot_views

class PilotAdminForm(forms.ModelForm):
    # Convert JSON field to more user-friendly format
    requirements_type = forms.ChoiceField(
        choices=[('text', 'Text Input'), ('file', 'File Upload')],
        initial='text',
        widget=forms.RadioSelect,
        required=False
    )
    requirements_text = forms.CharField(
        widget=forms.Textarea,
        required=False
    )
    requirements_file = forms.FileField(required=False)

    class Meta:
        model = Pilot
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        req_type = cleaned_data.get('requirements_type')
        req_text = cleaned_data.get('requirements_text')
        req_file = cleaned_data.get('requirements_file')

        # Structure the requirements as a list for the JSON field
        requirements = []
        if req_type == 'text' and req_text:
            requirements.append({
                'type': 'text',
                'content': req_text
            })
        elif req_type == 'file' and req_file:
            requirements.append({
                'type': 'file',
                'content': req_file.name
            })
        
        cleaned_data['requirements'] = requirements
        return cleaned_data

@admin.register(Pilot)
class PilotAdmin(admin.ModelAdmin):
    form = PilotAdminForm
    list_display = ('title', 'organization', 'status', 'price', 'verified', 'created_at')
    list_filter = ('status', 'organization', 'verified', 'legal_agreement_accepted')
    search_fields = ('title', 'description')
    
    fieldsets = (
        (None, {
            'fields': ('title', 'organization', 'pilot_definition', 'status', 'price')
        }),
        ('Details', {
            'fields': ('description', 'technical_specs_doc', 'technical_specs_text', 
                      'performance_metrics', 'performance_metrics_doc', 
                      'compliance_requirements', 'compliance_requirements_doc')
        }),
        ('Requirements', {
            'fields': ('requirements_type', 'requirements_text', 'requirements_file'),
            'description': 'Choose whether to accept text input or file uploads for requirements'
        }),
        ('Privacy', {
            'fields': ('is_private',)
        }),
        ('Verification', {
            'fields': ('legal_agreement_accepted', 'verified', 'admin_verified_at', 'admin_verified_by'),
        }),
    )
    
    readonly_fields = ('created_at', 'admin_verified_at',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            if hasattr(request.user, 'organization'):
                if request.user.organization.type == 'enterprise':
                    return qs.filter(organization=request.user.organization)
                elif request.user.organization.type == 'startup':
                    return qs
        return qs

    def has_add_permission(self, request):
        if not request.user.is_superuser:
            if hasattr(request.user, 'organization'):
                return request.user.organization.type == 'enterprise'
        return super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        if not request.user.is_superuser:
            if obj is None:
                return request.user.organization.type == 'enterprise'
            return obj.organization == request.user.organization
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_superuser:
            if obj is None:
                return request.user.organization.type == 'enterprise'
            return obj.organization == request.user.organization
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if not change:  # If this is a new pilot
            obj.organization = request.user.organization
        super().save_model(request, obj, form, change)

    def get_urls(self):
        """Add custom admin URLs for the enhanced workflow"""
        urls = super().get_urls()
        custom_urls = [
            # Main verification dashboard
            path('verify/', 
                 self.admin_site.admin_view(pilot_views.admin_verify_pilots), 
                 name='verify_pilots'),
            
            # Individual pilot verification
            path('verify/<int:pk>/', 
                 self.admin_site.admin_view(pilot_views.admin_verify_pilot_detail), 
                 name='verify_pilot_detail'),
            
            # Pilot approval actions
            path('verify/<int:pk>/approve/', 
                 self.admin_site.admin_view(pilot_views.admin_approve_pilot), 
                 name='approve_pilot'),
            
            path('verify/<int:pk>/reject/', 
                 self.admin_site.admin_view(pilot_views.admin_reject_pilot), 
                 name='reject_pilot'),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        """Add pilot verification stats to the changelist view"""
        extra_context = extra_context or {}
        
        # Add pilot verification stats
        extra_context['pilot_count_pending'] = Pilot.objects.filter(
            status='pending_approval', verified=False
        ).count()
        extra_context['verified_today'] = Pilot.objects.filter(
            verified=True, 
            admin_verified_at__date=timezone.now().date()
        ).count()
        extra_context['total_verified'] = Pilot.objects.filter(verified=True).count()
        extra_context['active_pilots_count'] = Pilot.objects.filter(
            status__in=['published', 'in_progress']
        ).count()
        extra_context['published_pilots_count'] = Pilot.objects.filter(
            status='published'
        ).count()
        
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(PilotBid)
class PilotBidAdmin(admin.ModelAdmin):
    list_display = ('id', 'pilot', 'startup', 'amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('pilot__title', 'startup__name')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['mark_as_live']
    
    fieldsets = (
        (None, {
            'fields': ('pilot', 'startup', 'amount', 'status')
        }),
        ('Proposal', {
            'fields': ('proposal',)
        }),
        ('Fees', {
            'fields': ('fee_percentage', 'startup_fee_percentage', 'enterprise_fee_percentage')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def mark_as_live(self, request, queryset):
        """Mark selected bids as live after payment verification"""
        # Only allow this action for approval_pending bids
        approval_pending = queryset.filter(status='approval_pending')
        if not approval_pending:
            self.message_user(request, "No approval pending bids were selected", level=messages.WARNING)
            return
            
        count = 0
        for bid in approval_pending:
            success = bid.mark_as_live()
            if success:
                count += 1
                
        self.message_user(request, f"{count} bid(s) marked as live successfully")
    
    mark_as_live.short_description = "Mark selected bids as live"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            if hasattr(request.user, 'organization'):
                if request.user.organization.type == 'enterprise':
                    # Enterprise sees bids on their pilots
                    return qs.filter(pilot__organization=request.user.organization)
                elif request.user.organization.type == 'startup':
                    # Startup sees their own bids
                    return qs.filter(startup=request.user.organization)
        return qs
    
    def has_change_permission(self, request, obj=None):
        if not request.user.is_superuser:
            if obj is None:
                return True  # Allow viewing the list
            # Only allow changing own bids
            if hasattr(request.user, 'organization'):
                if request.user.organization.type == 'enterprise':
                    return obj.pilot.organization == request.user.organization
                elif request.user.organization.type == 'startup':
                    return obj.startup == request.user.organization
            return False
        return super().has_change_permission(request, obj)
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Add custom context for bid admin actions"""
        extra_context = extra_context or {}
        bid = self.get_object(request, object_id)
        
        if bid:
            # Add context for showing admin actions
            extra_context['show_bid_info'] = True
            extra_context['show_admin_actions'] = request.user.is_staff
            
            # Show mark as live button if appropriate
            extra_context['show_mark_as_live_button'] = (
                bid.status == 'approval_pending' and request.user.is_staff
            )
        
        return super().change_view(request, object_id, form_url, extra_context=extra_context)
    
    def response_change(self, request, obj):
        """Handle custom admin actions"""
        if "_mark_as_live" in request.POST:
            success = obj.mark_as_live()
            if success:
                self.message_user(request, f"Bid for '{obj.pilot.title}' has been marked as live successfully")
            else:
                self.message_user(
                    request, 
                    f"Bid cannot be marked as live (current status: {obj.get_status_display()})", 
                    level=messages.ERROR
                )
            return HttpResponseRedirect(".")
            
        # Handle force status change (emergency override)
        if "_force_status" in request.POST:
            force_status = request.POST.get('force_status')
            if force_status and force_status in dict(obj.STATUS_CHOICES):
                old_status = obj.status
                obj.status = force_status
                obj.save(update_fields=['status', 'updated_at'])
                
                self.message_user(
                    request, 
                    f"Status forcefully changed from '{old_status}' to '{force_status}'"
                )
            return HttpResponseRedirect(".")
            
        return super().response_change(request, obj)

    def get_urls(self):
        """Add custom admin URLs for bid management"""
        urls = super().get_urls()
        custom_urls = [
            # Bid admin actions
            path('<int:pk>/mark-as-live/', 
                 self.admin_site.admin_view(pilot_views.admin_mark_bid_as_live), 
                 name='mark_bid_as_live'),
        ]
        return custom_urls + urls