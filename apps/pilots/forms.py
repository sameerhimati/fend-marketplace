from django import forms
from .models import PilotBid

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
        pilot = self.initial.get('pilot')
        
        if pilot and amount < pilot.price:
            raise forms.ValidationError(
                f"Your bid amount (${amount}) is less than the pilot's required price (${pilot.price})."
            )
        
        return amount