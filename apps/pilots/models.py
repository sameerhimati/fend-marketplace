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
    # Simplified but complete status choices
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved - Payment Pending'),
        ('live', 'Live - Work in Progress'),
        ('completion_pending', 'Completion Pending Review'),
        ('completed', 'Completed'),
        ('declined', 'Declined'),
    ]

    # Core relationships and bid details
    pilot = models.ForeignKey(Pilot, on_delete=models.CASCADE, related_name='bids')
    startup = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE, related_name='submitted_bids')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    proposal = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Fee structure - CRITICAL for financial calculations
    fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    startup_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    enterprise_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    
    # Audit timestamps - ESSENTIAL for compliance
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Stripe integration
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        unique_together = ['pilot', 'startup']
    
    def approve_bid(self):
        """Enterprise approves bid - handles complete approval workflow"""
        if self.status not in ['pending', 'under_review']:
            return False
        
        # Decline competing bids
        self._decline_competing_bids()
        
        # Update bid status
        old_status = self.status
        self.status = 'approved'
        self.save(update_fields=['status', 'updated_at'])
        
        # Update pilot status
        self.pilot.status = 'in_progress'
        self.pilot.save(update_fields=['status'])
        
        # Create escrow payment
        self._create_escrow_payment()
        
        # Send notifications
        self._notify_bid_approved()
        
        return True
    
    def mark_live(self):
        """Admin marks bid as live after payment verification"""
        if self.status != 'approved':
            return False
        
        self.status = 'live'
        self.save(update_fields=['status', 'updated_at'])
        
        self._notify_work_can_begin()
        return True
    
    def request_completion(self):
        """Startup requests completion verification"""
        if self.status != 'live':
            return False
        
        self.status = 'completion_pending'
        self.save(update_fields=['status', 'updated_at'])
        
        self._notify_completion_requested()
        return True
    
    def verify_completion(self):
        """Enterprise verifies work completion"""
        if self.status != 'completion_pending':
            return False
        
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'updated_at', 'completed_at'])
        
        # Update pilot status
        self.pilot.status = 'completed'
        self.pilot.save(update_fields=['status'])
        
        self._notify_completion_verified()
        return True
    
    def decline_bid(self, declined_by_enterprise=True):
        """Decline the bid with proper notification"""
        if self.status not in ['pending', 'under_review']:
            return False
        
        self.status = 'declined'
        self.save(update_fields=['status', 'updated_at'])
        
        self._notify_bid_declined(declined_by_enterprise)
        return True
    
    # Financial calculations - CRITICAL for payment processing
    def calculate_total_amount_for_enterprise(self):
        """Calculate total amount enterprise needs to pay (includes enterprise fee)"""
        enterprise_fee = (self.amount * self.enterprise_fee_percentage) / 100
        return self.amount + enterprise_fee
    
    def calculate_startup_net_amount(self):
        """Calculate net amount startup receives (after startup fee)"""
        startup_fee = (self.amount * self.startup_fee_percentage) / 100
        return self.amount - startup_fee
    
    def calculate_platform_fee(self):
        """Calculate total platform fee"""
        return (self.amount * (self.startup_fee_percentage + self.enterprise_fee_percentage)) / 100
    
    # Status checks for workflow control
    def can_be_approved(self):
        return self.status in ['pending', 'under_review']
    
    def can_be_declined(self):
        return self.status in ['pending', 'under_review']
    
    def can_request_completion(self):
        return self.status == 'live'
    
    def can_verify_completion(self):
        return self.status == 'completion_pending'
    
    def is_active(self):
        """Check if bid is in an active workflow state"""
        return self.status in ['approved', 'live', 'completion_pending', 'completed']
    
    # Private helper methods
    def _decline_competing_bids(self):
        """Auto-decline other pending bids when this one is approved"""
        competing_bids = PilotBid.objects.filter(
            pilot=self.pilot,
            status__in=['pending', 'under_review']
        ).exclude(id=self.id)
        
        for bid in competing_bids:
            bid.decline_bid(declined_by_enterprise=False)
    
    def _create_escrow_payment(self):
        """Create escrow payment record with calculated amounts"""
        from apps.payments.models import EscrowPayment
        
        total_amount = self.calculate_total_amount_for_enterprise()
        startup_amount = self.amount  # Full bid amount before fees
        platform_fee = self.calculate_platform_fee()
        
        EscrowPayment.objects.create(
            pilot_bid=self,
            total_amount=total_amount,
            startup_amount=startup_amount,
            platform_fee=platform_fee,
            enterprise_fee_percentage=self.enterprise_fee_percentage,
            startup_fee_percentage=self.startup_fee_percentage,
            status='pending'
        )
    
    # Notification methods - ESSENTIAL for transparency
    def _notify_bid_approved(self):
        from apps.notifications.services import create_bid_notification, create_admin_notification
        
        # Notify both parties
        create_bid_notification(
            bid=self,
            notification_type='bid_approved',
            title=f"Bid Approved: {self.pilot.title}",
            message=f"The bid for '${self.amount}' on pilot '{self.pilot.title}' has been approved. Fend will send payment instructions shortly."
        )
        
        # Notify admin to generate invoice
        create_admin_notification(
            title=f"Generate Invoice: {self.pilot.title}",
            message=f"Approved bid for '${self.amount}' on pilot '{self.pilot.title}'. Enterprise: {self.pilot.organization.name}. Total payment required: ${self.calculate_total_amount_for_enterprise()}",
            related_pilot=self.pilot,
            related_bid=self
        )
    
    def _notify_work_can_begin(self):
        from apps.notifications.services import create_bid_notification
        create_bid_notification(
            bid=self,
            notification_type='work_can_begin',
            title=f"Work Can Begin: {self.pilot.title}",
            message=f"Payment has been verified for pilot '{self.pilot.title}'. Work can now begin."
        )
    
    def _notify_completion_requested(self):
        from apps.notifications.services import create_pilot_notification
        create_pilot_notification(
            pilot=self.pilot,
            notification_type='completion_requested',
            title=f"Completion Review Requested: {self.pilot.title}",
            message=f"The startup has completed work on pilot '{self.pilot.title}' and requests verification of completion."
        )
    
    def _notify_completion_verified(self):
        from apps.notifications.services import create_admin_notification, create_bid_notification
        
        # Notify admin to release payment
        create_admin_notification(
            title=f"Release Payment: {self.pilot.title}",
            message=f"Work completed and verified for pilot '{self.pilot.title}'. Ready to release ${self.calculate_startup_net_amount()} to {self.startup.name}.",
            related_pilot=self.pilot,
            related_bid=self
        )
        
        # Notify both parties
        create_bid_notification(
            bid=self,
            notification_type='work_completed',
            title=f"Work Completed: {self.pilot.title}",
            message=f"Work for pilot '{self.pilot.title}' has been completed and verified. Payment will be released soon."
        )
    
    def _notify_bid_declined(self, declined_by_enterprise):
        from apps.notifications.services import create_bid_notification
        
        if declined_by_enterprise:
            message = f"Your bid of ${self.amount} for pilot '{self.pilot.title}' has been declined by the enterprise."
        else:
            message = f"Your bid of ${self.amount} for pilot '{self.pilot.title}' was automatically declined because another bid was accepted."
        
        create_bid_notification(
            bid=self,
            notification_type='bid_declined',
            title=f"Bid Declined: {self.pilot.title}",
            message=message
        )
    
    def get_status_context(self):
        """Get user-friendly status information for templates"""
        status_context = {
            'pending': {
                'message': 'Waiting for enterprise review',
                'next_action': 'Enterprise will review your proposal',
                'color': 'yellow'
            },
            'under_review': {
                'message': 'Under review by enterprise',
                'next_action': 'Enterprise is evaluating your proposal',
                'color': 'blue'
            },
            'approved': {
                'message': 'Bid approved - payment verification pending',
                'next_action': 'Fend is processing payment before work can begin',
                'color': 'orange'
            },
            'live': {
                'message': 'Payment verified - work in progress',
                'next_action': 'Complete the work and request verification',
                'color': 'green'
            },
            'completion_pending': {
                'message': 'Completion verification pending',
                'next_action': 'Enterprise is reviewing your completed work',
                'color': 'purple'
            },
            'completed': {
                'message': 'Work completed and verified',
                'next_action': 'Payment will be released soon',
                'color': 'emerald'
            },
            'declined': {
                'message': 'Bid was declined',
                'next_action': 'You may submit a new bid if permitted',
                'color': 'red'
            }
        }
        return status_context.get(self.status, {})
    
    def __str__(self):
        return f"Bid by {self.startup.name} for {self.pilot.title} - ${self.amount}"