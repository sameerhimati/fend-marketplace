from django import forms
from .models import Pilot, PilotBid

class PilotForm(forms.ModelForm):
    class Meta:
        model = Pilot
        fields = ['title', 'description', 'technical_specs_doc', 'performance_metrics', 
                  'compliance_requirements', 'is_private', 'price']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'required': True}),
            'performance_metrics': forms.Textarea(attrs={'rows': 3, 'required': True}),
            'compliance_requirements': forms.Textarea(attrs={'rows': 3, 'required': True}),
            'price': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'required': True}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mark all fields as required
        self.fields['title'].required = True
        self.fields['description'].required = True
        self.fields['technical_specs_doc'].required = True
        self.fields['performance_metrics'].required = True
        self.fields['compliance_requirements'].required = True
        self.fields['price'].required = True
        
        # Set help text
        self.fields['technical_specs_doc'].help_text = "Upload technical specifications document (required)"
        self.fields['performance_metrics'].help_text = "Define quantifiable performance metrics and KPIs (required)"
        self.fields['compliance_requirements'].help_text = "Specify the definition of done for this pilot (required)"

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