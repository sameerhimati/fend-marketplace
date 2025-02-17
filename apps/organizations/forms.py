from django import forms
from .models import Organization, PilotDefinition

class OrganizationBasicForm(forms.ModelForm):
    """First step of organization registration"""

    website = forms.CharField(max_length=255)

    class Meta:
        model = Organization
        fields = ['name', 'type', 'website']

    def clean_website(self):
        website = self.cleaned_data['website']
        if not website.startswith(('http://', 'https://')):
            website = 'https://' + website
        return website

class EnterpriseDetailsForm(forms.ModelForm):
    """Second step for enterprise organizations"""
    class Meta:
        model = Organization
        fields = [
            'business_type',
            'business_registration_number',
            'tax_identification_number',
            'primary_contact_name',
            'primary_contact_email',
            'primary_contact_phone'
        ]

class PilotDefinitionForm(forms.ModelForm):
    """Optional third step for enterprise pilot definition"""
    class Meta:
        model = PilotDefinition
        fields = [
            'description',
            'technical_specs_doc',
            'performance_metrics',
            'compliance_requirements',
            'is_private'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'performance_metrics': forms.Textarea(attrs={'rows': 4}),
            'compliance_requirements': forms.Textarea(attrs={'rows': 4}),
        }