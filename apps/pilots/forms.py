from django import forms
from .models import Pilot, PilotBid
import os

class PilotForm(forms.ModelForm):
    # Add choice fields for input type
    technical_specs_type = forms.ChoiceField(
        choices=[('file', 'Upload Document'), ('text', 'Enter Text')],
        initial='file',
        widget=forms.RadioSelect,
        required=False
    )
    
    performance_metrics_type = forms.ChoiceField(
        choices=[('file', 'Upload Document'), ('text', 'Enter Text')],
        initial='file',
        widget=forms.RadioSelect,
        required=False
    )
    
    compliance_requirements_type = forms.ChoiceField(
        choices=[('file', 'Upload Document'), ('text', 'Enter Text')],
        initial='file',
        widget=forms.RadioSelect,
        required=False
    )
    
    class Meta:
        model = Pilot
        fields = ['title', 'description', 'technical_specs_doc', 'technical_specs_text',
                'performance_metrics', 'performance_metrics_doc', 
                'compliance_requirements', 'compliance_requirements_doc',
                'is_private', 'price', 
                'technical_specs_type', 'performance_metrics_type', 'compliance_requirements_type']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'required': True}),
            'technical_specs_text': forms.Textarea(attrs={'rows': 3}),
            'performance_metrics': forms.Textarea(attrs={'rows': 3}),
            'compliance_requirements': forms.Textarea(attrs={'rows': 3}),
            'price': forms.NumberInput(attrs={
                'min': '1000',
                'step': '100',
                'placeholder': '5000',
                'required': True,
            })
        }
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validate and clean the uploaded documents
        cleaned_data['technical_specs_doc'] = self.clean_doc('technical_specs_doc')
        cleaned_data['performance_metrics_doc'] = self.clean_doc('performance_metrics_doc')
        cleaned_data['compliance_requirements_doc'] = self.clean_doc('compliance_requirements_doc')
        
        return cleaned_data
    
    def clean_doc(self, file_field_name):
        """Validate uploaded documents"""
        file = self.cleaned_data.get(file_field_name)
        if file:
            # Check file extension
            ext = os.path.splitext(file.name)[1].lower()
            valid_extensions = ['.pdf', '.doc', '.docx', '.txt', '.xls', '.xlsx']
            if ext not in valid_extensions:
                raise forms.ValidationError(
                    f'File type not supported. Allowed types: {", ".join(valid_extensions)}'
                )
            
            # Check file size (10MB limit)
            if file.size > 10 * 1024 * 1024:
                raise forms.ValidationError('File too large. Size should not exceed 10MB.')
        
        return file
    
    def clean_technical_specs_doc(self):
        return self.clean_doc('technical_specs_doc')
    
    def clean_performance_metrics_doc(self):
        return self.clean_doc('performance_metrics_doc')
    
    def clean_compliance_requirements_doc(self):
        return self.clean_doc('compliance_requirements_doc')

class PilotBidForm(forms.ModelForm):
    class Meta:
        model = PilotBid
        fields = ['amount', 'proposal']
        widgets = {
            'proposal': forms.Textarea(attrs={
                'rows': 6,
                'class': 'shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md',
                'placeholder': 'Describe your implementation approach, timeline, and why your startup is the best fit...'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md',
                'placeholder': 'Enter bid amount in USD',
                'min': '1000',
                'step': '100',
            })
        }
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise forms.ValidationError("Bid amount must be greater than zero.")
        
        return amount