from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django import forms
from .models import Pilot, PilotBid
from django.urls import path
from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.contrib.admin import AdminSite
from django.http import HttpResponseRedirect
from django.urls import reverse
from .models import Pilot, PilotBid
from apps.notifications.services import create_pilot_notification, create_notification

class CustomAdminSite(AdminSite):
    """Custom admin site that adds pilot verification counts to the index context"""
    
    def index(self, request, extra_context=None):
        """Add pilot count to the admin index"""
        if extra_context is None:
            extra_context = {}
            
        # Add pilot count
        pilot_count_pending = Pilot.objects.filter(status='pending_approval', verified=False).count()
        extra_context['pilot_count_pending'] = pilot_count_pending
        
        return super().index(request, extra_context)

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
            'fields': ('description', 'technical_specs_doc', 'technical_specs_text', 'performance_metrics', 'performance_metrics_doc', 'compliance_requirements', 'compliance_requirements_doc')
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
        urls = super().get_urls()
        custom_urls = [
            path('verify/', self.admin_site.admin_view(self.verify_pilots_view), name='admin_verify_pilots'),
            path('verify/<int:pk>/', self.admin_site.admin_view(self.verify_pilot_detail_view), name='admin_verify_pilot_detail'),
            path('verify/<int:pk>/approve/', self.admin_site.admin_view(self.approve_pilot_view), name='admin_approve_pilot'),
            path('verify/<int:pk>/reject/', self.admin_site.admin_view(self.reject_pilot_view), name='admin_reject_pilot'),
        ]
        return custom_urls + urls
        
    def verify_pilots_view(self, request):
        """Admin view for pilot verification dashboard"""
        pending_pilots = Pilot.objects.filter(status='pending_approval', verified=False)
        
        # Get stats for the dashboard
        verified_today = Pilot.objects.filter(
            verified=True, 
            admin_verified_at__date=timezone.now().date()
        ).count()
        
        total_verified = Pilot.objects.filter(verified=True).count()
        
        context = {
            **self.admin_site.each_context(request),
            'title': 'Pilot Verification',
            'pending_pilots': pending_pilots,
            'verified_today': verified_today,
            'total_verified': total_verified,
            'opts': self.model._meta,
        }
        return TemplateResponse(request, 'admin/pilots/pilot/verify.html', context)
        
    def verify_pilot_detail_view(self, request, pk):
        """Admin view for pilot verification detail"""
        pilot = get_object_or_404(Pilot, pk=pk)
        
        context = {
            **self.admin_site.each_context(request),
            'title': f'Verify Pilot: {pilot.title}',
            'pilot': pilot,
            'opts': self.model._meta,
        }
        return TemplateResponse(request, 'admin/pilots/pilot/verify_detail.html', context)
    
    def approve_pilot_view(self, request, pk):
        """Admin view to approve a pilot"""
        if request.method != 'POST':
            return HttpResponseRedirect(reverse('admin:admin_verify_pilot_detail', args=[pk]))
            
        pilot = get_object_or_404(Pilot, pk=pk)
        
        # Update pilot status
        pilot.status = 'published'
        pilot.verified = True
        pilot.admin_verified_at = timezone.now()
        pilot.admin_verified_by = request.user
        pilot.published_at = timezone.now()
        pilot.save()
        
        # Create notification for enterprise
        create_pilot_notification(
            pilot=pilot,
            notification_type='pilot_approved',
            title=f"Pilot approved: {pilot.title}",
            message=f"Your pilot '{pilot.title}' has been approved and is now visible to startups."
        )
        
        self.message_user(request, f"Pilot '{pilot.title}' has been approved and published.")
        return HttpResponseRedirect(reverse('admin:admin_verify_pilots'))
    
    def reject_pilot_view(self, request, pk):
        """Admin view to reject a pilot"""
        if request.method != 'POST':
            return HttpResponseRedirect(reverse('admin:admin_verify_pilot_detail', args=[pk]))
            
        pilot = get_object_or_404(Pilot, pk=pk)
        feedback = request.POST.get('feedback', 'No specific feedback provided')
        
        # Update pilot status back to draft
        pilot.status = 'draft'
        pilot.save()
        
        # Create notification for enterprise with feedback
        create_pilot_notification(
            pilot=pilot,
            notification_type='pilot_rejected',
            title=f"Pilot needs revision: {pilot.title}",
            message=f"Your pilot '{pilot.title}' needs revision before it can be published. Admin feedback: {feedback}"
        )
        
        self.message_user(request, f"Pilot '{pilot.title}' has been rejected and sent back to draft status.")
        return HttpResponseRedirect(reverse('admin:admin_verify_pilots'))


@admin.register(PilotBid)
class PilotBidAdmin(admin.ModelAdmin):
    list_display = ('id', 'pilot', 'startup', 'amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('pilot__title', 'startup__name')
    readonly_fields = ('created_at', 'updated_at')
    
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