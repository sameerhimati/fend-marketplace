from django import forms
from .models import Organization, PilotDefinition

class OrganizationBasicForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ['name', 'type', 'website']

    def clean_website(self):
        website = self.cleaned_data.get('website', '').strip().lower()
        if not website:
            return website
            
        # Remove http:// or https:// if present
        if website.startswith('http://'):
            website = website[7:]
        elif website.startswith('https://'):
            website = website[8:]
        
        # Remove www. if present
        if website.startswith('www.'):
            website = website[4:]
            
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