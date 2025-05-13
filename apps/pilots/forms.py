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
                  'is_private', 'price']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'required': True}),
            'technical_specs_text': forms.Textarea(attrs={'rows': 3}),
            'performance_metrics': forms.Textarea(attrs={'rows': 3}),
            'compliance_requirements': forms.Textarea(attrs={'rows': 3}),
            'price': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'required': True}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validate technical specs (either file or text required)
        tech_type = cleaned_data.get('technical_specs_type', 'file')
        tech_file = cleaned_data.get('technical_specs_doc')
        tech_text = cleaned_data.get('technical_specs_text')
        
        if tech_type == 'file' and not tech_file and not self.instance.technical_specs_doc:
            raise forms.ValidationError({'technical_specs_doc': 'Technical specifications document is required'})
        elif tech_type == 'text' and not tech_text and not self.instance.technical_specs_text:
            raise forms.ValidationError({'technical_specs_text': 'Technical specifications text is required'})
        
        # Validate performance metrics (either file or text required)
        perf_type = cleaned_data.get('performance_metrics_type', 'file')
        perf_file = cleaned_data.get('performance_metrics_doc')
        perf_text = cleaned_data.get('performance_metrics')
        
        if perf_type == 'file' and not perf_file and not self.instance.performance_metrics_doc:
            raise forms.ValidationError({'performance_metrics_doc': 'Performance metrics document is required'})
        elif perf_type == 'text' and not perf_text and not self.instance.performance_metrics:
            raise forms.ValidationError({'performance_metrics': 'Performance metrics text is required'})
        
        # Validate compliance requirements (either file or text required)
        comp_type = cleaned_data.get('compliance_requirements_type', 'file')
        comp_file = cleaned_data.get('compliance_requirements_doc')
        comp_text = cleaned_data.get('compliance_requirements')
        
        if comp_type == 'file' and not comp_file and not self.instance.compliance_requirements_doc:
            raise forms.ValidationError({'compliance_requirements_doc': 'Compliance requirements document is required'})
        elif comp_type == 'text' and not comp_text and not self.instance.compliance_requirements:
            raise forms.ValidationError({'compliance_requirements': 'Compliance requirements text is required'})
        
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
                'placeholder': 'Enter bid amount in USD'
            })
        }
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise forms.ValidationError("Bid amount must be greater than zero.")
        
        return amount