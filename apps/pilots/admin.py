from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django import forms
from .models import Pilot

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
    list_display = ('title', 'organization', 'status', 'created_at')
    list_filter = ('status', 'organization')
    search_fields = ('title', 'description')
    
    fieldsets = (
        (None, {
            'fields': ('title', 'organization', 'pilot_definition', 'status')
        }),
        ('Details', {
            'fields': ('description', 'technical_specs_doc', 'performance_metrics', 'compliance_requirements')
        }),
        ('Requirements', {
            'fields': ('requirements_type', 'requirements_text', 'requirements_file'),
            'description': 'Choose whether to accept text input or file uploads for requirements'
        }),
        ('Privacy', {
            'fields': ('is_private',)
        })
    )

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