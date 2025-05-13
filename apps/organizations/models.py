from django.db import models
from django.core.validators import URLValidator
from django.db.models.signals import post_save
from apps.payments.models import Subscription
from django.conf import settings
from django.dispatch import receiver
import phonenumbers



class Organization(models.Model):
    ORGANIZATION_TYPES = (
        ('enterprise', 'Enterprise'),
        ('startup', 'Startup'),
    )
    
    BUSINESS_TYPES = (
        ('', 'Select One'),
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

    description = models.TextField(blank=True, null=True, help_text="Company description")
    logo = models.ImageField(upload_to='organization_logos/', blank=True, null=True)

    # Primary Contact Info
    primary_contact_name = models.CharField(max_length=255, null=True, blank=True)
    # primary_contact_email = models.EmailField(null=True, blank=True)
    primary_contact_phone = models.CharField(max_length=20, null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    onboarding_completed = models.BooleanField(default=False)

    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)
    has_payment_method = models.BooleanField(default=False)
    free_trial_used = models.BooleanField(default=False)

    bank_name = models.CharField(max_length=255, blank=True, null=True)
    bank_account_number = models.CharField(max_length=255, blank=True, null=True)
    bank_routing_number = models.CharField(max_length=255, blank=True, null=True)
    
    published_pilot_count = models.IntegerField(default=0, help_text="Number of published pilots")

    def has_active_subscription(self):
        """
        Check if the organization has an active subscription.
        
        Returns:
            bool: True if the organization has an active subscription, False otherwise.
        """
        try:
            # Check if the organization has a subscription relation
            if not hasattr(self, 'subscription'):
                return False
                
            # Check if the subscription exists and is active
            return self.subscription is not None and self.subscription.status == 'active'
        except Exception:
            # Handle any errors gracefully
            return False
        
    def get_remaining_pilots(self):
        """Get number of remaining pilots that can be published"""
        try:
            subscription = self.subscription
            if not subscription.is_active():
                return 0
                
            if subscription.plan.pilot_limit is None:
                return float('inf')  # Unlimited
            
            remaining = max(0, subscription.plan.pilot_limit - self.published_pilot_count)
            return remaining
        except (Subscription.DoesNotExist, AttributeError):
            return 0
    
    def can_publish_more_pilots(self):
        """Check if organization can publish more pilots"""
        remaining = self.get_remaining_pilots()
        return remaining > 0 or remaining == float('inf')
    
    def increment_published_pilots(self):
        """Increment the published pilot count. Returns True if successful."""
        if self.can_publish_more_pilots():
            self.published_pilot_count += 1
            self.save(update_fields=['published_pilot_count'])
            return True
        return False
        
    def can_create_pilot(self):
        """Check if the organization can create new pilots (draft only)"""
        if self.type != 'enterprise':
            return False
        
        # Only need platform access (active subscription) to create draft pilots
        return self.has_active_subscription()
            
    def can_publish_pilot(self):
        """Check if the organization can publish pilots (requires available pilot slots)"""
        if not self.can_create_pilot():
            return False
            
        # Check if organization has available pilot slots
        return self.can_publish_more_pilots()

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

@receiver(post_save, sender=Organization)
def create_stripe_customer(sender, instance, created, **kwargs):
    """Create a Stripe customer when a new organization is created"""
    if created and not instance.stripe_customer_id:
        try:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            # Find a user associated with this organization
            user = instance.members.first()
            
            if user:
                customer = stripe.Customer.create(
                    email=user.email,
                    name=instance.name,
                    metadata={
                        'organization_id': instance.id,
                        'organization_type': instance.type
                    }
                )
                
                instance.stripe_customer_id = customer.id
                instance.save(update_fields=['stripe_customer_id'])
        except Exception as e:
            print(f"Error creating Stripe customer: {e}")

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