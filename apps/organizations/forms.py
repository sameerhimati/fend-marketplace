from django import forms
from django.contrib.auth import get_user_model
from .models import Organization, PilotDefinition

User = get_user_model()

class OrganizationBasicForm(forms.ModelForm):
    # Add user fields
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = Organization
        fields = ['name', 'type', 'website']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        email = cleaned_data.get('email')

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords don't match")
        
        # Check if email is already in use
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already registered")
            
        return cleaned_data

    def clean_website(self):
        # Your existing website cleaning logic
        website = self.cleaned_data.get('website', '').strip().lower()
        if not website:
            return website
            
        if website.startswith('http://'):
            website = website[7:]
        elif website.startswith('https://'):
            website = website[8:]
        
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