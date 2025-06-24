# Legal acceptance tracking fields for Organization model
# Add these fields to the Organization model in models.py

from django.db import models

# Legal document acceptance tracking fields
legal_acceptance_fields = {
    # Terms of Service
    'terms_of_service_accepted': models.BooleanField(default=False),
    'terms_of_service_accepted_at': models.DateTimeField(null=True, blank=True),
    
    # Privacy Policy
    'privacy_policy_accepted': models.BooleanField(default=False),
    'privacy_policy_accepted_at': models.DateTimeField(null=True, blank=True),
    
    # User Agreement
    'user_agreement_accepted': models.BooleanField(default=False),
    'user_agreement_accepted_at': models.DateTimeField(null=True, blank=True),
    
    # Payment Terms
    'payment_terms_accepted': models.BooleanField(default=False),
    'payment_terms_accepted_at': models.DateTimeField(null=True, blank=True),
    
    # Payment Holding Service Agreement
    'payment_holding_agreement_accepted': models.BooleanField(default=False),
    'payment_holding_agreement_accepted_at': models.DateTimeField(null=True, blank=True),
    
    # Data Processing Agreement (EU users)
    'data_processing_agreement_accepted': models.BooleanField(default=False),
    'data_processing_agreement_accepted_at': models.DateTimeField(null=True, blank=True),
    
    # Product Listing and Commission Agreement
    'product_listing_agreement_accepted': models.BooleanField(default=False),
    'product_listing_agreement_accepted_at': models.DateTimeField(null=True, blank=True),
}

# Helper methods to add to Organization model
def has_required_legal_acceptances(self):
    """Check if organization has accepted all required legal documents for registration"""
    required_docs = [
        'terms_of_service_accepted',
        'privacy_policy_accepted', 
        'user_agreement_accepted'
    ]
    
    # EU users also need data processing agreement
    if self.is_eu_based():
        required_docs.append('data_processing_agreement_accepted')
    
    return all(getattr(self, field) for field in required_docs)

def has_payment_legal_acceptances(self):
    """Check if organization has accepted payment-related legal documents"""
    payment_docs = [
        'payment_terms_accepted',
        'payment_holding_agreement_accepted'
    ]
    return all(getattr(self, field) for field in payment_docs)

def has_deals_legal_acceptances(self):
    """Check if organization has accepted deals program legal documents"""
    return self.product_listing_agreement_accepted

def is_eu_based(self):
    """Check if organization is EU-based (simple check based on country)"""
    # This is a simplified check - you may want to enhance this
    eu_countries = ['DE', 'FR', 'ES', 'IT', 'NL', 'BE', 'AT', 'PL', 'SE', 'DK', 'FI', 'IE', 'GB']
    # Extract country code from headquarters_location or use a dedicated country field
    return any(code in (self.headquarters_location or '') for code in eu_countries)

def accept_legal_document(self, document_type):
    """Accept a legal document and record timestamp"""
    from django.utils import timezone
    
    accepted_field = f"{document_type}_accepted"
    timestamp_field = f"{document_type}_accepted_at"
    
    if hasattr(self, accepted_field) and hasattr(self, timestamp_field):
        setattr(self, accepted_field, True)
        setattr(self, timestamp_field, timezone.now())
        self.save(update_fields=[accepted_field, timestamp_field])
        return True
    return False