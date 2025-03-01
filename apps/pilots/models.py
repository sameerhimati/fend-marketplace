# apps/pilots/models.py
from django.db import models
from apps.organizations.models import Organization, PilotDefinition
from django.core.exceptions import ValidationError
from apps.payments.models import PilotTransaction

class Pilot(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    # Link to the organization creating the pilot
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='pilots'
    )
    
    # Link to the organization's pilot definition template
    pilot_definition = models.ForeignKey(
        PilotDefinition,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_pilots'
    )

    # Pilot specific fields
    title = models.CharField(max_length=255)
    description = models.TextField()
    requirements = models.JSONField(default=list)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    
    # Auto-populated from PilotDefinition but can be overridden
    technical_specs_doc = models.FileField(
        upload_to='pilot_specs/',
        null=True,
        blank=True
    )
    performance_metrics = models.TextField(null=True, blank=True)
    compliance_requirements = models.TextField(null=True, blank=True)
    is_private = models.BooleanField(default=False)

    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=False,  # Make it required
        blank=False,
        default=0,  # Default to 0
        help_text="Enter the fixed price for this pilot (in USD)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Check if this is a new pilot being published
        if self.pk is None and self.status == 'published':
            # Check if organization can create a new pilot
            if not self.organization.can_create_pilot():
                raise ValidationError(
                    "Your organization has reached its pilot limit or doesn't have an active subscription."
                )
        
        # If status is changing from draft to published
        if self.pk and self.status == 'published':
            original = Pilot.objects.get(pk=self.pk)
            if original.status == 'draft':
                # Check if organization can create a new pilot
                if not self.organization.can_create_pilot():
                    raise ValidationError(
                        "Your organization has reached its pilot limit or doesn't have an active subscription."
                    )
        super().save(*args, **kwargs)
    
    def is_editable(self):
        """Check if pilot can be edited"""
        return self.status in ['draft', 'published']

    def is_viewable_by(self, user):
        """Check if a user can view this pilot"""
        if user.is_superuser:
            return True
        
        user_org = user.organization
        if user_org.type == 'enterprise':
            return self.organization == user_org
        elif user_org.type == 'startup':
            return (not self.is_private and self.status == 'published')
        return False

    def can_be_edited_by(self, user):
        """Check if a user can edit this pilot"""
        if user.is_superuser:
            return True
                
        user_org = user.organization
        # Allow enterprises to edit their own pilots regardless of status
        return user_org.type == 'enterprise' and self.organization == user_org

    def get_formatted_requirements(self):
        """Return requirements in a formatted way"""
        if not self.requirements:
            return []
        
        formatted = []
        for req in self.requirements:
            if isinstance(req, dict):
                req_type = req.get('type', 'text')
                content = req.get('content', '')
                formatted.append({
                    'type': req_type,
                    'content': content
                })
        return formatted
    

class PilotBid(models.Model):

    fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=5.00, help_text="Transaction fee percentage")

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('declined', 'Declined'),
        ('completed', 'Completed'),  # Add this status for completed pilots
        ('paid', 'Paid')
    ]

    pilot = models.ForeignKey(Pilot, on_delete=models.CASCADE, related_name='bids')
    startup = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE, related_name='submitted_bids')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    proposal = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # For stripe integration
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        unique_together = ['pilot', 'startup']
    
    def mark_as_completed(self):
        """Mark the bid as completed and create transaction"""
        from payments.models import PilotTransaction
        
        # Only approved bids can be completed
        if self.status != 'approved':
            return False
        # Create or update transaction
        transaction, created = PilotTransaction.objects.get_or_create(
            pilot_bid=self,
            defaults={
                'amount': self.amount,
                'fee_percentage': self.fee_percentage,
                'fee_amount': (self.amount * self.fee_percentage) / 100,
                'status': 'pending'
            }
        )
        
        # Update status
        self.status = 'completed'
        self.save()
        
        return transaction