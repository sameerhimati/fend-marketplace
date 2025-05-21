# apps/pilots/models.py
from django.db import models
from apps.organizations.models import Organization, PilotDefinition
from django.core.exceptions import ValidationError
from apps.payments.models import PilotTransaction
from django.utils import timezone as timezone
from django.utils.text import slugify
import os
import decimal


def pilot_technical_doc_path(instance, filename):
    """Generate path for technical specs documents"""
    org_slug = slugify(instance.organization.name)
    pilot_id = instance.pk or 'temp'
    ext = os.path.splitext(filename)[1]
    safe_filename = f"technical_{slugify(instance.title[:30])}{ext}"
    return f'pilot_specs/{org_slug}/{pilot_id}/technical/{safe_filename}'

def pilot_performance_doc_path(instance, filename):
    """Generate path for performance metrics documents"""
    org_slug = slugify(instance.organization.name)
    pilot_id = instance.pk or 'temp'
    ext = os.path.splitext(filename)[1]
    safe_filename = f"performance_{slugify(instance.title[:30])}{ext}"
    return f'pilot_specs/{org_slug}/{pilot_id}/performance/{safe_filename}'

def pilot_compliance_doc_path(instance, filename):
    """Generate path for compliance requirements documents"""
    org_slug = slugify(instance.organization.name)
    pilot_id = instance.pk or 'temp'
    ext = os.path.splitext(filename)[1]
    safe_filename = f"compliance_{slugify(instance.title[:30])}{ext}"
    return f'pilot_specs/{org_slug}/{pilot_id}/compliance/{safe_filename}'

class Pilot(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
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
    
    technical_specs_doc = models.FileField(
        upload_to=pilot_technical_doc_path,
        null=True,
        blank=True
    )

    technical_specs_text = models.TextField(null=True, blank=True)

    performance_metrics_doc = models.FileField(
        upload_to=pilot_performance_doc_path,
        null=True,
        blank=True
    )

    performance_metrics = models.TextField(null=True, blank=True)

    compliance_requirements_doc = models.FileField(
        upload_to=pilot_compliance_doc_path,
        null=True,
        blank=True
    )

    compliance_requirements = models.TextField(
    null=True, 
    blank=True,
    help_text="Specify the definition of done for this pilot"
)
    is_private = models.BooleanField(default=False)

    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=False,  # Make it required
        blank=False,
        default=1000,  # Default to 0
        help_text="Enter the fixed price for this pilot (in USD)"
    )

    legal_agreement_accepted = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    admin_verified_at = models.DateTimeField(null=True, blank=True)
    admin_verified_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_pilots'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    published_at = models.DateTimeField(null=True, blank=True, help_text="When the pilot was published")
    
    def save(self, *args, **kwargs):
        # Check if this is a new pilot being published
        is_new_publication = False
        
        if self.pk is None and self.status == 'published':
            is_new_publication = True
        elif self.pk:
            # Check if status is changing from draft to published
            original = Pilot.objects.get(pk=self.pk)
            if original.status != 'published' and self.status == 'published':
                is_new_publication = True
        
        # If new publication, validate and increment pilot count
        if is_new_publication:
            # Check if organization can publish a pilot
            if not self.organization.can_publish_pilot():
                if self.organization.get_remaining_pilots() == 0:
                    raise ValidationError(
                        "You've reached your plan's pilot limit. Please upgrade to publish more pilots."
                    )
                else:
                    raise ValidationError(
                        "Your organization doesn't have an active subscription. Please subscribe to publish pilots."
                    )
            
            # Set published_at timestamp
            self.published_at = timezone.now()
            
            # Mark that this will increment the pilot count
            self._increment_pilot_count = True
            
        super().save(*args, **kwargs)
        
        # After successful save, increment pilot count if needed
        if hasattr(self, '_increment_pilot_count') and self._increment_pilot_count:
            self.organization.increment_published_pilots()
            delattr(self, '_increment_pilot_count')

    def __str__(self):
        return self.title

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
    # Adjust fee_percentage field and add new fields for split fees
    fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=10.00, help_text="Total transaction fee percentage")
    startup_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=5.00, help_text="Startup's portion of transaction fee")
    enterprise_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=5.00, help_text="Enterprise's portion of transaction fee")

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('approval_pending', 'Approval Pending'),
        ('approved', 'Approved'),
        ('live', 'Live'),
        ('declined', 'Declined'),
        ('completion_pending', 'Completion Pending'),
        ('completed', 'Completed'),
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
    
    def mark_as_approved(self):
        """Mark bid as approval_pending and notify admin"""
        if self.status != 'pending' and self.status != 'under_review':
            return False
        
        # Update bid status to approval_pending
        self.status = 'approval_pending'
        self.save()
        
        # Handle other pending bids - decline them
        other_pending_bids = PilotBid.objects.filter(
            pilot=self.pilot,
            status__in=['pending', 'under_review']
        ).exclude(id=self.id)
        
        if other_pending_bids.exists():
            from apps.notifications.services import create_bid_notification
            for bid in other_pending_bids:
                bid.status = 'declined'
                bid.save()
                
                # Create notification
                create_bid_notification(
                    bid=bid,
                    notification_type='bid_updated',
                    title=f"Bid Declined: {bid.pilot.title}",
                    message=f"Another bid has been accepted for '{bid.pilot.title}', so your bid has been declined."
                )

        # Create notification for both parties
        from apps.notifications.services import create_bid_notification
        create_bid_notification(
            bid=self,
            notification_type='bid_updated',
            title=f"Bid Approved: {self.pilot.title}",
            message=f"The bid for '{self.pilot.title}' has been approved and is pending payment verification. The Fend team will send an invoice shortly."
        )
        
        # Create notification for admin
        from apps.notifications.services import create_notification
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Notify admins about the approved bid
        admins = User.objects.filter(is_staff=True)
        for admin in admins:
            create_notification(
                recipient=admin,
                notification_type='bid_approved',
                title=f"New Bid Approved: {self.pilot.title}",
                message=f"A bid for '{self.pilot.title}' has been approved by {self.pilot.organization.name}. Amount: ${self.amount}. Please generate an invoice.",
                related_pilot=self.pilot,
                related_bid=self
            )
        
        return True
    

    def mark_as_live(self):
        """Mark bid as live after payment verification and admin kickoff"""
        if self.status != 'approval_pending':
            return False
        
        self.status = 'live'
        self.save()
        
        # Update pilot status to in_progress
        pilot = self.pilot
        pilot.status = 'in_progress'
        pilot.save(update_fields=['status'])
        
        # Create notification for both parties
        from apps.notifications.services import create_bid_notification
        create_bid_notification(
            bid=self,
            notification_type='bid_live',
            title=f"Pilot is now Live: {self.pilot.title}",
            message=f"Your pilot '{self.pilot.title}' has been verified and is now live. You may begin work now."
        )
        
        return True
    
    def mark_completion_requested(self):
        """Startup marks work as complete, awaiting enterprise verification"""
        if self.status != 'live':
            return False
        
        self.status = 'completion_pending'
        self.save()
        
        # Create notifications for enterprise
        from apps.notifications.services import create_bid_notification
        create_bid_notification(
            bid=self,
            notification_type='completion_requested',
            title=f"Completion Requested: {self.pilot.title}",
            message=f"The startup has marked the pilot '{self.pilot.title}' as completed. Please review and verify completion."
        )
        return True

    def verify_completion(self):
        """Enterprise verifies the work is completed satisfactorily"""
        if self.status != 'completion_pending':
            return False
        
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
        
        # Also update pilot status
        pilot = self.pilot
        pilot.status = 'completed'
        pilot.save(update_fields=['status'])
        
        # Notify admin for payment release
        from apps.notifications.services import create_notification
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admins = User.objects.filter(is_staff=True)
        for admin in admins:
            create_notification(
                recipient=admin,
                notification_type='pilot_completed',
                title=f"Pilot Verified Complete: {self.pilot.title}",
                message=f"The pilot '{self.pilot.title}' has been verified as completed by the enterprise. The payment is ready to be released.",
                related_pilot=self.pilot,
                related_bid=self
            )
        
        # Notify both parties
        from apps.notifications.services import create_bid_notification
        create_bid_notification(
            bid=self,
            notification_type='pilot_completed',
            title=f"Pilot Completion Verified: {self.pilot.title}",
            message=f"The pilot '{self.pilot.title}' has been verified as completed by the enterprise. The payment will be released soon."
        )
        
        return True