from django.contrib import admin
from django import forms
from .models import Organization, PilotDefinition

class PilotDefinitionInline(admin.StackedInline):
    model = PilotDefinition
    can_delete = False
    verbose_name_plural = 'Pilot Definition'

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'business_type', 'primary_contact_name', 'onboarding_completed')
    list_filter = ('type', 'business_type', 'onboarding_completed')
    search_fields = ('name', 'primary_contact_name', 'primary_contact_email')
    
    inlines = [PilotDefinitionInline]

    fieldsets = [
        ('Basic Information', {
            'fields': ('name', 'type', 'website')
        }),
        ('Business Information', {
            'fields': (
                'business_type',
                'business_registration_number',
                'tax_identification_number'
            ),
            'classes': ('enterprise-only',)
        }),
        ('Primary Contact', {
            'fields': (
                'primary_contact_name',
                # 'primary_contact_email',
                'primary_contact_phone'
            ),
            'classes': ('enterprise-only',)
        }),
        ('Status', {
            'fields': ('onboarding_completed',)
        })
    ]

    class Media:
        js = ('admin/js/organization_type_toggle.js',)
        css = {
            'all': ('admin/css/organization_admin.css',)
        }

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