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
    

def clean_business_registration_number(self):
    brn = self.cleaned_data.get('business_registration_number')
    
    if not brn:
        return brn
    
    # Strip out non-alphanumeric characters
    brn_clean = ''.join(e for e in brn if e.isalnum())
    
    # EIN format: XX-XXXXXXX (9 digits)
    if len(brn_clean) != 9 or not brn_clean.isdigit():
        raise forms.ValidationError(
            "EIN must be in the format XX-XXXXXXX (9 digits total)."
        )
    
    # Format as XX-XXXXXXX
    formatted_brn = f"{brn_clean[:2]}-{brn_clean[2:]}"
    return formatted_brn

def clean_tax_identification_number(self):
    tin = self.cleaned_data.get('tax_identification_number')
    
    if not tin:
        return tin
    
    # Strip out non-alphanumeric characters
    tin_clean = ''.join(e for e in tin if e.isalnum())
    
    # EIN format: XX-XXXXXXX (9 digits)
    if len(tin_clean) != 9 or not tin_clean.isdigit():
        raise forms.ValidationError(
            "EIN must be in the format XX-XXXXXXX (9 digits total)."
        )
    
    # Format as XX-XXXXXXX
    formatted_tin = f"{tin_clean[:2]}-{tin_clean[2:]}"
    return formatted_tin

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
        widgets = {
            'business_registration_number': forms.TextInput(
                attrs={
                    'placeholder': 'XX-XXXXXXX',
                    'pattern': r'\d{2}-\d{7}',
                    'title': 'Format: XX-XXXXXXX (9 digits total)'
                }
            ),
            'tax_identification_number': forms.TextInput(
                attrs={
                    'placeholder': 'XX-XXXXXXX',
                    'pattern': r'\d{2}-\d{7}',
                    'title': 'Format: XX-XXXXXXX (9 digits total)'
                }
            ),
        }
    
    clean_business_registration_number = clean_business_registration_number
    clean_tax_identification_number = clean_tax_identification_number

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