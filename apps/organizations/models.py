from django.db import models
from django.core.validators import URLValidator
from django.db.models.signals import post_save
from django.dispatch import receiver
import phonenumbers

class Organization(models.Model):
    ORGANIZATION_TYPES = (
        ('enterprise', 'Enterprise'),
        ('startup', 'Startup'),
    )
    
    BUSINESS_TYPES = (
        ('c_corp', 'C-Corporation'),
        ('s_corp', 'S-Corporation'),
        ('llc', 'LLC'),
        ('international', 'International'),
    )

    # Basic Organization Info
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=ORGANIZATION_TYPES)
    website = models.CharField(max_length=255)
    business_type = models.CharField(
        max_length=20, 
        choices=BUSINESS_TYPES,
        null=True,
        blank=True
    )
    business_registration_number = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Format: country-code-number"
    )
    tax_identification_number = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    # Primary Contact Info
    primary_contact_name = models.CharField(max_length=255, null=True, blank=True)
    # primary_contact_email = models.EmailField(null=True, blank=True)
    primary_contact_phone = models.CharField(max_length=20, null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    onboarding_completed = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    def clean(self):
        from django.core.exceptions import ValidationError
        
        # Only validate enterprise-specific fields if type is enterprise 
        # AND onboarding_completed is True (means they've gone through all steps)
        if self.type == 'enterprise' and self.onboarding_completed:
            required_fields = [
                'business_type',
                'business_registration_number',
                'tax_identification_number',
                'primary_contact_name',
                'primary_contact_email',
                'primary_contact_phone'
            ]
            
            for field in required_fields:
                if not getattr(self, field):
                    raise ValidationError(f"{field.replace('_', ' ').title()} is required for enterprise organizations.")

            # Validate phone number format
            try:
                if self.primary_contact_phone:
                    parsed_number = phonenumbers.parse(self.primary_contact_phone, None)
                    if not phonenumbers.is_valid_number(parsed_number):
                        raise ValidationError("Invalid phone number format")
            except phonenumbers.NumberParseException:
                raise ValidationError("Invalid phone number format")

class PilotDefinition(models.Model):
    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name='pilot_definition'
    )
    
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Provide a detailed description of the pilot"
    )
    
    # Technical Specifications
    technical_specs_doc = models.FileField(
        upload_to='pilot_specs/',
        null=True,
        blank=True
    )
    
    # Performance Metrics
    performance_metrics = models.TextField(
        null=True,
        blank=True,
        help_text="Define quantifiable performance metrics and KPIs"
    )
    
    # Compliance Requirements
    compliance_requirements = models.TextField(
        null=True,
        blank=True,
        help_text="Specify explicit compliance requirements for production launch"
    )
    
    is_private = models.BooleanField(
        default=False,
        help_text="Make this pilot definition private"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Pilot Definition for {self.organization.name}"