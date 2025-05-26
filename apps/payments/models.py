from django.db import models
from django.conf import settings
from django.utils import timezone

import stripe

class PricingPlan(models.Model):
    """Defines available pricing plans for different organization types"""
    PLAN_TYPES = (
        ('startup_monthly', 'Startup Monthly'),
        ('startup_yearly', 'Startup Yearly'),
        ('enterprise_monthly', 'Enterprise Monthly'),
        ('enterprise_yearly', 'Enterprise Yearly'),
    )
    
    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=50, choices=PLAN_TYPES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    billing_frequency = models.CharField(
        max_length=20,
        choices=[
            ('monthly', 'Monthly'),
            ('yearly', 'Yearly'),
        ]
    )
    stripe_price_id = models.CharField(max_length=100)
    pilot_limit = models.IntegerField(null=True, blank=True, 
                                     help_text="Maximum number of published pilots allowed (null = unlimited)")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'payments_pricingplan'
    
    def __str__(self):
        limit_text = f"{self.pilot_limit} pilots" if self.pilot_limit else "Unlimited pilots"
        return f"{self.name} (${self.price}/{self.billing_frequency}, {limit_text})"
    
    @classmethod
    def get_available_plans(cls, organization_type):
        """Return available plans for an organization type"""
        if organization_type == 'startup':
            return cls.objects.filter(
                plan_type__in=['startup_monthly', 'startup_yearly'],
                is_active=True
            )
        elif organization_type == 'enterprise':
            return cls.objects.filter(
                plan_type__in=['enterprise_monthly', 'enterprise_yearly'],
                is_active=True
            )
        return cls.objects.none()


class Subscription(models.Model):
    """Tracks an organization's subscription status"""
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
        ('trialing', 'Trialing'),
        ('incomplete', 'Incomplete'),
        ('incomplete_expired', 'Incomplete Expired'),
        ('unpaid', 'Unpaid'),
    )
    
    organization = models.OneToOneField(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='subscription'
    )
    plan = models.ForeignKey(
        PricingPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions'
    )
    stripe_subscription_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='incomplete')
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.organization.name} - {self.plan.name}"
    
    def is_active(self):
        """Check if subscription is active"""
        return self.status == 'active' and self.current_period_end > timezone.now()
    
    def remaining_pilots(self):
        """Get number of pilots that can still be published"""
        if not self.is_active():
            return 0
            
        if self.plan.pilot_limit is None:
            return float('inf')  # Unlimited
        
        published = self.organization.published_pilot_count
        return max(0, self.plan.pilot_limit - published)

    def can_create_pilot(self):
        """Check if subscription allows creating pilots (draft)"""
        return self.is_active()
        
    def display_limit(self):
        """Human-readable representation of the pilot limit"""
        if self.plan.pilot_limit is None:
            return "Unlimited"
        return str(self.plan.pilot_limit)
    
    def cancel(self):
        """Cancel subscription in Stripe"""
        if not self.stripe_subscription_id:
            self.status = 'canceled'
            self.save()
            return True
        
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            stripe.Subscription.delete(self.stripe_subscription_id)
            self.status = 'canceled'
            self.save()
            return True
        except Exception as e:
            print(f"Error canceling subscription: {e}")
            return False


class Payment(models.Model):
    """Tracks payment history"""
    PAYMENT_TYPES = (
        ('subscription', 'Subscription'),
        ('pilot_fee', 'Pilot Fee'),
    )
    
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='payments'
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments'
    )
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    stripe_payment_id = models.CharField(max_length=100)
    status = models.CharField(max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.organization.name} - ${self.amount} ({self.payment_type})"


class PilotTransaction(models.Model):
    """Track completed pilot transactions and fees"""
    pilot_bid = models.OneToOneField(
        'pilots.PilotBid', 
        on_delete=models.CASCADE,
        related_name='transaction'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    fee_amount = models.DecimalField(max_digits=10, decimal_places=2)
    fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    stripe_payment_intent_id = models.CharField(max_length=100)
    status = models.CharField(max_length=20, default='pending')
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Transaction for Bid #{self.pilot_bid.id} - ${self.amount}"
    
    def calculate_fee(self):
        """Calculate the fee for this transaction"""
        return (self.amount * self.fee_percentage) / 100

class EscrowPayment(models.Model):
    # Updated 4-stage workflow status choices
    STATUS_CHOICES = (
        ('pending', 'Invoice Pending'),           # Stage 1: Waiting for admin to generate invoice
        ('instructions_sent', 'Invoice Sent'),    # Stage 2: Invoice sent to enterprise  
        ('received', 'Payment Received & Work Active'), # Stage 3: Payment confirmed and work activated
        ('released', 'Released to Startup'),      # Stage 4: Payment released to startup
        ('cancelled', 'Cancelled')                # Payment cancelled
    )
    
    # Core relationships and amounts
    pilot_bid = models.OneToOneField(
        'pilots.PilotBid',
        on_delete=models.CASCADE,
        related_name='escrow_payment'
    )
    reference_code = models.CharField(max_length=50, unique=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    startup_amount = models.DecimalField(max_digits=10, decimal_places=2) 
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2) 
    enterprise_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    startup_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    
    # Status and audit timestamps - CRITICAL for financial compliance
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    instructions_sent_at = models.DateTimeField(null=True, blank=True)
    # Keep this field for backward compatibility but don't use it in new workflow
    payment_initiated_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    
    # Payment tracking - for status only (actual payment handled externally)
    payment_reference = models.CharField(max_length=255, null=True, blank=True, help_text="External payment reference")
    
    # Admin tracking - CRITICAL for audit trail
    admin_notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Escrow Payment {self.reference_code} - ${self.total_amount}"
    
    def generate_reference_code(self):
        """Generate unique reference code for payment tracking"""
        import time
        import random
        prefix = "FND-PILOT"
        bid_id = self.pilot_bid.id
        # Use current timestamp + small random number to ensure uniqueness
        timestamp = int(time.time())
        random_suffix = random.randint(100, 999)
        return f"{prefix}-{bid_id}-{timestamp}-{random_suffix}"
    
    def save(self, *args, **kwargs):
        # Generate reference code before first save if it doesn't exist
        if not self.pk and not self.reference_code:
            self.reference_code = self.generate_reference_code()
        return super().save(*args, **kwargs)
    
    def mark_as_instructions_sent(self, user=None):
        """Admin marks payment instructions as sent"""
        old_status = self.status
        self.status = 'instructions_sent'
        self.instructions_sent_at = timezone.now()
        self.save(update_fields=['status', 'instructions_sent_at'])
        
        # Log the change
        EscrowPaymentLog.log_status_change(self, old_status, user, "Payment instructions sent to enterprise")
        
        # Notify enterprise
        self._notify_instructions_sent()
    
    def mark_as_received_and_activate(self, user=None, notes=None):
        """Admin confirms payment received AND activates work in one step"""
        old_status = self.status
        self.status = 'received'
        self.received_at = timezone.now()
        if notes:
            self.admin_notes = notes
        self.save(update_fields=['status', 'received_at', 'admin_notes'])
        
        # Log the change
        EscrowPaymentLog.log_status_change(self, old_status, user, f"Payment received and work activated. {notes or ''}")
        
        # Mark bid as live so work can begin
        self.pilot_bid.mark_live()
        
        # Notify both parties with SHORTENED notification types
        self._notify_payment_received_and_activated()
    
    def mark_as_released(self, user=None, notes=None):
        """Admin releases payment to startup"""
        if self.status != 'received':
            return False
        
        old_status = self.status
        self.status = 'released'
        self.released_at = timezone.now()
        if notes:
            self.admin_notes = (self.admin_notes or '') + f"\n{notes}"
        self.save(update_fields=['status', 'released_at', 'admin_notes'])
        
        # Log the change
        EscrowPaymentLog.log_status_change(self, old_status, user, f"Payment released to startup. {notes or ''}")
        
        # Notify both parties
        self._notify_payment_released()
        
        return True
    
    def cancel_payment(self, reason=None, user=None):
        """Cancel the escrow payment"""
        old_status = self.status
        self.status = 'cancelled'
        if reason:
            self.admin_notes = (self.admin_notes or '') + f"\nCancelled: {reason}"
        self.save(update_fields=['status', 'admin_notes'])
        
        # Log the change
        EscrowPaymentLog.log_status_change(self, old_status, user, f"Payment cancelled. Reason: {reason or 'No reason provided'}")
        
        # Notify parties
        self._notify_payment_cancelled()
    
    # Updated payment workflow status checks for 4-stage workflow
    def can_send_instructions(self):
        return self.status == 'pending'
    
    def can_confirm_and_activate(self):
        """Can move directly from instructions_sent to received & activated"""
        return self.status == 'instructions_sent'
    
    def can_release(self):
        return self.status == 'received'
    
    # Notification methods - essential for transparency
    def _notify_instructions_sent(self):
        from apps.notifications.services import create_pilot_notification
        create_pilot_notification(
            pilot=self.pilot_bid.pilot,
            notification_type='payment_instructions',
            title=f"Invoice Generated: {self.pilot_bid.pilot.title}",
            message=f"Invoice for ${self.total_amount} has been generated for pilot '{self.pilot_bid.pilot.title}'. Reference: {self.reference_code}"
        )
    
    def _notify_payment_received_and_activated(self):
        """Notify both parties that payment was received and work is activated"""
        from apps.notifications.services import create_notification
        
        # Notify enterprise - SHORTENED notification type
        for user in self.pilot_bid.pilot.organization.users.all():
            create_notification(
                recipient=user,
                notification_type='payment_verified', 
                title=f"Payment Verified & Work Activated: {self.pilot_bid.pilot.title}",
                message=f"Your payment for pilot '{self.pilot_bid.pilot.title}' has been verified and work has been activated. {self.pilot_bid.startup.name} can now begin work.",
                related_pilot=self.pilot_bid.pilot,
                related_bid=self.pilot_bid
            )
        
        # Notify startup - SHORTENED notification type  
        for user in self.pilot_bid.startup.users.all():
            create_notification(
                recipient=user,
                notification_type='work_activated',
                title=f"Payment Verified - Work Activated: {self.pilot_bid.pilot.title}",
                message=f"Great news! Payment has been verified for pilot '{self.pilot_bid.pilot.title}' and work is now live. You can begin immediately.",
                related_pilot=self.pilot_bid.pilot,
                related_bid=self.pilot_bid
            )

    def _notify_payment_released(self):
        from apps.notifications.services import create_bid_notification
        create_bid_notification(
            bid=self.pilot_bid,
            notification_type='payment_released',
            title=f"Payment Released: {self.pilot_bid.pilot.title}",
            message=f"Payment of ${self.startup_amount} has been released for completed pilot '{self.pilot_bid.pilot.title}'."
        )
    
    def _notify_payment_cancelled(self):
        from apps.notifications.services import create_bid_notification
        create_bid_notification(
            bid=self.pilot_bid,
            notification_type='payment_cancelled',
            title=f"Payment Cancelled: {self.pilot_bid.pilot.title}",
            message=f"Payment for pilot '{self.pilot_bid.pilot.title}' has been cancelled. {self.admin_notes or ''}"
        )


class EscrowPaymentLog(models.Model):
    """Comprehensive audit log for escrow payments - REQUIRED for compliance"""
    escrow_payment = models.ForeignKey(
        EscrowPayment,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    previous_status = models.CharField(max_length=20, null=True, blank=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='escrow_payment_logs'
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Payment {self.escrow_payment.reference_code}: {self.previous_status} → {self.new_status}"
    
    @classmethod
    def log_status_change(cls, escrow_payment, previous_status, changed_by=None, notes=None):
        """Create audit log entry for status changes"""
        return cls.objects.create(
            escrow_payment=escrow_payment,
            previous_status=previous_status,
            new_status=escrow_payment.status,
            changed_by=changed_by,
            notes=notes
        )
    
    class Meta:
        ordering = ['-created_at']