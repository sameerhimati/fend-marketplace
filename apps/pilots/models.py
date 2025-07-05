# apps/pilots/models.py
from django.db import models
from apps.organizations.models import Organization, PilotDefinition
from django.core.exceptions import ValidationError
from django.utils import timezone as timezone
from django.core.validators import MinValueValidator
from django.utils.text import slugify
from fend.storage_backends import get_pilot_document_storage
import os
import decimal


def pilot_technical_doc_path(instance, filename):
    """Generate path for technical specs documents"""
    org_slug = slugify(instance.organization.name)
    pilot_id = instance.pk or 'temp'
    
    # Store original filename for later retrieval
    instance._original_technical_filename = filename
    
    # Create a clean filename that preserves original name
    name, ext = os.path.splitext(filename)
    safe_name = slugify(name[:50])  # Keep more of the original name
    safe_filename = f"technical_{safe_name}{ext}"
    return f'documents/pilots/{org_slug}/{pilot_id}/technical/{safe_filename}'

def pilot_performance_doc_path(instance, filename):
    """Generate path for performance metrics documents"""
    org_slug = slugify(instance.organization.name)
    pilot_id = instance.pk or 'temp'
    
    # Store original filename for later retrieval
    instance._original_performance_filename = filename
    
    # Create a clean filename that preserves original name
    name, ext = os.path.splitext(filename)
    safe_name = slugify(name[:50])  # Keep more of the original name
    safe_filename = f"performance_{safe_name}{ext}"
    return f'documents/pilots/{org_slug}/{pilot_id}/performance/{safe_filename}'

def pilot_compliance_doc_path(instance, filename):
    """Generate path for compliance requirements documents"""
    org_slug = slugify(instance.organization.name)
    pilot_id = instance.pk or 'temp'
    
    # Store original filename for later retrieval
    instance._original_compliance_filename = filename
    
    # Create a clean filename that preserves original name
    name, ext = os.path.splitext(filename)
    safe_name = slugify(name[:50])  # Keep more of the original name
    safe_filename = f"compliance_{safe_name}{ext}"
    return f'documents/pilots/{org_slug}/{pilot_id}/compliance/{safe_filename}'

def pilot_bid_doc_path(instance, filename):
    """Generate path for pilot bid documents"""
    org_slug = slugify(instance.startup.name)
    pilot_slug = slugify(instance.pilot.title)
    bid_id = instance.pk or 'temp'
    
    # Store original filename for later retrieval
    instance._original_proposal_filename = filename
    
    # Create a clean filename that preserves original name
    name, ext = os.path.splitext(filename)
    safe_name = slugify(name[:50])  # Keep more of the original name
    safe_filename = f"proposal_{safe_name}_{bid_id}{ext}"
    return f'documents/bids/{org_slug}/{pilot_slug}/{safe_filename}'

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
        storage=get_pilot_document_storage,
        null=True,
        blank=True
    )

    technical_specs_text = models.TextField(null=True, blank=True)

    performance_metrics_doc = models.FileField(
        upload_to=pilot_performance_doc_path,
        storage=get_pilot_document_storage,
        null=True,
        blank=True
    )

    performance_metrics = models.TextField(null=True, blank=True)

    compliance_requirements_doc = models.FileField(
        upload_to=pilot_compliance_doc_path,
        storage=get_pilot_document_storage,
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
        default=5000.00,
        validators=[MinValueValidator(1000.00, message="Pilot price must be at least $1,000")],
        help_text="Enter the fixed price for this pilot (in USD)"
    )

    legal_agreement_accepted = models.BooleanField(default=False)

    # Featured content ordering
    featured_order = models.PositiveIntegerField(
        default=999,
        help_text="Order for featured sections (lower numbers appear first, 0 = highest priority)"
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
            # Check if status is changing from any status to published
            original = Pilot.objects.get(pk=self.pk)
            if original.status != 'published' and self.status == 'published':
                is_new_publication = True
        
        # If new publication, validate and increment pilot count
        if is_new_publication:
            # Skip validation if this is an admin approval
            if not getattr(self, '_admin_approval', False):
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
            # Startups can view published pilots (including private ones via direct link)
            # Private pilots don't show in listings but are accessible via direct URL
            return self.status == 'published'
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
    
    def get_user_relationship(self, user):
        """
        Determine the relationship between a user and this pilot.
        Returns dict with relationship info and actions.
        """
        if not user.is_authenticated:
            return {'type': 'none'}
        
        # Handle admin/staff users who don't have organizations
        if user.is_staff or user.is_superuser:
            return {'type': 'admin', 'can_view_all': True}
        
        if not hasattr(user, 'organization') or user.organization is None:
            return {'type': 'none'}
        
        user_org = user.organization
        
        # Enterprise owns this pilot
        if user_org == self.organization:
            relationship = {
                'type': 'owner',
                'can_edit': self.status in ['draft', 'published'],
                'can_delete': self.status == 'draft',
            }
            
            # Check for bids on this pilot
            bids = self.bids.all().order_by('-created_at')
            if bids.exists():
                pending_bids = bids.filter(status__in=['pending', 'under_review'])
                approved_bids = bids.filter(status__in=['approved', 'live', 'completion_pending', 'completed'])
                
                relationship.update({
                    'bids_count': bids.count(),
                    'pending_bids_count': pending_bids.count(),
                    'approved_bids_count': approved_bids.count(),
                    'bids': bids,
                    'has_approved_bid': approved_bids.exists(),
                })
                
                if approved_bids.exists():
                    active_bid = approved_bids.first()
                    relationship.update({
                        'active_bid': active_bid,
                        'working_agreement': {
                            'startup': active_bid.startup,
                            'amount': active_bid.amount,
                            'proposal': active_bid.proposal,
                            'status': active_bid.status,
                        }
                    })
            
            return relationship
        
        # Startup viewing this pilot
        elif user_org.type == 'startup':
            # Check if they have a bid on this pilot
            try:
                user_bid = self.bids.get(startup=user_org)
                relationship = {
                    'type': 'bidder',
                    'bid': user_bid,
                    'bid_status': user_bid.status,
                    'can_withdraw': user_bid.status == 'pending',
                    'can_edit': user_bid.status == 'pending',
                    'can_resubmit': user_bid.status == 'declined',
                }
                
                # If bid is active, treat it as the active bid
                if user_bid.is_active():
                    relationship['active_bid'] = user_bid
                
                # If bid is approved/active, show working agreement
                if user_bid.status in ['approved', 'live', 'completion_pending', 'completed']:
                    relationship.update({
                        'working_agreement': {
                            'amount': user_bid.amount,
                            'proposal': user_bid.proposal,
                            'status': user_bid.status,
                            'enterprise': self.organization,
                        }
                    })
                if user_bid.status == 'declined' and user_bid.rejection_reason:
                    relationship['rejection_reason'] = user_bid.rejection_reason
                
                return relationship
            except:
                # No bid from this startup
                # Check if pilot is available for bidding
                if (self.status == 'published' and 
                    not self.is_private and 
                    not self.bids.filter(status__in=['approved', 'live', 'completion_pending', 'completed']).exists()):
                    return {
                        'type': 'available',
                        'can_bid': True,
                    }
                else:
                    return {
                        'type': 'unavailable',
                        'can_bid': False,
                        'reason': 'Already has approved bid' if self.bids.filter(status__in=['approved', 'live', 'completion_pending', 'completed']).exists() else 'Not available'
                    }
        
        return {'type': 'viewer'}

    def get_display_summary(self, user):
        """
        Get a summary for list display based on user relationship
        """
        relationship = self.get_user_relationship(user)
        
        if relationship['type'] == 'owner':
            if relationship.get('bids_count', 0) > 0:
                if relationship.get('has_approved_bid'):
                    active_bid = relationship['active_bid']
                    return f"Active work with {active_bid.startup.name} - {active_bid.get_status_display()}"
                else:
                    return f"{relationship['pending_bids_count']} bid(s) pending review"
            else:
                return "Available for bids"
        
        elif relationship['type'] == 'bidder':
            bid = relationship['bid']
            if bid.status in ['approved', 'live', 'completion_pending', 'completed']:
                return f"Your work - {bid.get_status_display()}"
            else:
                return f"Your bid - {bid.get_status_display()}"
        
        elif relationship['type'] == 'available':
            return "Available to bid"
        
        elif relationship['type'] == 'unavailable':
            return relationship.get('reason', 'Not available')
        
        return ""

    def get_next_action(self, user):
        """
        Get the next action the user can take on this pilot
        """
        relationship = self.get_user_relationship(user)
        
        if relationship['type'] == 'owner':
            if relationship.get('pending_bids_count', 0) > 0:
                return "Review bids"
            elif relationship.get('has_approved_bid'):
                active_bid = relationship['active_bid']
                if active_bid.status == 'completion_pending':
                    return "Verify completion"
                elif active_bid.status in ['approved', 'live']:
                    return "Track progress"
            return "Manage pilot"
        
        elif relationship['type'] == 'bidder':
            bid = relationship['bid']
            if bid.status == 'live':
                return "Request completion"
            elif bid.status in ['pending', 'under_review']:
                return "Track bid status"
            return "View details"
        
        elif relationship['type'] == 'available':
            return "Submit bid"
        
        return "View details"
    
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
    proposal_doc = models.FileField(
        upload_to=pilot_bid_doc_path,
        storage=get_pilot_document_storage,
        null=True,
        blank=True,
        help_text="Optional: Upload a document to supplement your proposal"
    )
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

    rejection_reason = models.TextField(null=True, blank=True, help_text="Reason for rejection provided by enterprise")
    
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
        
        # Create payment holding service
        self._create_payment_holding_service()
        
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
    
    def decline_bid_with_reason(self, declined_by_enterprise=True, reason=None):
        """Decline the bid with a detailed reason"""
        if self.status not in ['pending', 'under_review']:
            return False
        
        self.status = 'declined'
        if reason:
            self.rejection_reason = reason
        self.save(update_fields=['status', 'updated_at', 'rejection_reason'])
        
        self._notify_bid_declined_with_reason(declined_by_enterprise, reason)
        return True
    
    def decline_bid(self, declined_by_enterprise=True):
        """Original decline method for backward compatibility"""
        return self.decline_bid_with_reason(declined_by_enterprise)
    
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
            bid.decline_bid_with_reason(declined_by_enterprise=False)
    
    def _create_payment_holding_service(self):
        """Create payment holding service record with calculated amounts"""
        from apps.payments.models import EscrowPayment
        
        total_amount = self.calculate_total_amount_for_enterprise()
        startup_amount = self.calculate_startup_net_amount()  # Net amount after startup fee
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
            message=f"Your ${self.amount} bid for '{self.pilot.title}' has been approved! Payment instructions will be sent shortly."
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
            notification_type='bid_live',
            title=f"🚀 Ready to Start: {self.pilot.title}",
            message=f"Payment confirmed! You can now begin work on '{self.pilot.title}'."
        )
    
    def _notify_completion_requested(self):
        from apps.notifications.services import create_pilot_notification
        create_pilot_notification(
            pilot=self.pilot,
            notification_type='completion_requested',
            title=f"✅ Review Requested: {self.pilot.title}",
            message=f"{self.startup.name} has completed work on '{self.pilot.title}' and is requesting final review."
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
            title=f"🎉 Work Completed: {self.pilot.title}",
            message=f"Congratulations! Work on '{self.pilot.title}' has been approved and payment will be released shortly."
        )
    
    def _notify_bid_declined_with_reason(self, declined_by_enterprise, reason=None):
        """Enhanced notification with rejection reason"""
        from apps.notifications.services import create_bid_notification
        
        if declined_by_enterprise:
            base_message = f"Your bid of ${self.amount} for pilot '{self.pilot.title}' has been declined by the enterprise."
            if reason:
                message = f"{base_message}\n\nReason: {reason}\n\nYou can submit a revised bid if you'd like to address the feedback."
            else:
                message = f"{base_message}\n\nYou can submit a new bid if you'd like."
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