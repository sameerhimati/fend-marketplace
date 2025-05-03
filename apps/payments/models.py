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
    initial_tokens = models.IntegerField(default=0)  # Initial tokens provided with the plan
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'payments_pricingplan'
    
    def __str__(self):
        return f"{self.name} (${self.price}/{self.billing_frequency})"
    
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
        """
        Legacy method maintained for backward compatibility.
        Pilot limits are no longer used with the token system.
        """
        return float('inf')  # Always return infinite pilots available

    def can_create_pilot(self):
        """
        Legacy method maintained for backward compatibility.
        Now just checks if subscription is active.
        """
        return self.is_active()
    
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
    

class TokenPackage(models.Model):
    """Defines available token packages for purchase"""
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=100)  # Base price per token
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    stripe_price_id = models.CharField(max_length=100, blank=True, null=True)
    token_count = models.PositiveIntegerField(default=1)
    
    class Meta:
        ordering = ['price']
    
    def __str__(self):
        return f"{self.name} (${self.price} per token)"
    
    def get_quantity_price(self):
        return self.price
    
    def calculate_total_price(self, quantity):
        """Calculate total price for a quantity of tokens with discount applied"""
        return self.get_quantity_price() * quantity
    
    @classmethod
    def get_default_package(cls):
        """Return the default token package (or create if doesn't exist)"""
        package, created = cls.objects.get_or_create(
            name="Standard Token",
            defaults={
                "price": 100.00,
                "description": "Tokens for publishing pilot opportunities",
                "is_active": True
            }
        )
        return package

    @classmethod
    def get_available_packages(cls):
        """Get all active token packages"""
        return cls.objects.filter(is_active=True).order_by('price')


class TokenTransaction(models.Model):
    """Records token purchase transactions"""
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='token_transactions'
    )
    package = models.ForeignKey(
        TokenPackage,
        on_delete=models.SET_NULL,
        null=True,
        related_name='transactions'
    )
    token_count = models.IntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    stripe_payment_id = models.CharField(max_length=100)
    stripe_checkout_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(
        max_length=20, 
        choices=[
            ('pending', 'Pending'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
            ('failed', 'Failed')
        ],
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.organization.name} - {self.token_count} tokens (${self.amount})"
        
    def mark_completed(self):
        """Mark transaction as completed and add tokens to organization"""
        if self.status != 'completed':
            self.status = 'completed'
            self.completed_at = timezone.now()
            self.save()
            
            # Add tokens to organization
            self.organization.add_tokens(self.token_count)
            
            # Create notification for successful token purchase
            from apps.notifications.services import create_notification
            create_notification(
                recipient=self.organization.members.first(),  # Send to first member (likely admin)
                notification_type='payment_received',
                title=f"Token Purchase Successful",
                message=f"Your purchase of {self.token_count} tokens has been completed successfully."
            )

class TokenConsumptionLog(models.Model):
    """Records detailed token consumption events"""
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='token_consumption_logs'
    )
    tokens_consumed = models.IntegerField(default=1)
    action_type = models.CharField(
        max_length=50,
        choices=[
            ('pilot_publish', 'Pilot Publication'),
            ('other', 'Other Consumption')
        ],
        default='pilot_publish'
    )
    pilot = models.ForeignKey(
        'pilots.Pilot',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='token_consumptions'
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.organization.name} - {self.tokens_consumed} tokens on {self.created_at.strftime('%Y-%m-%d')}"


class EscrowPayment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),        # Initial state when created
        ('instructions_sent', 'Instructions Sent'),  # Payment instructions sent to enterprise
        ('payment_initiated', 'Payment Initiated'),  # Enterprise marked as sent
        ('received', 'Received'),      # Admin confirmed payment received
        ('released', 'Released'),      # Funds released to startup
        ('cancelled', 'Cancelled')     # Payment cancelled
    )
    
    pilot_bid = models.OneToOneField(
        'pilots.PilotBid',
        on_delete=models.CASCADE,
        related_name='escrow_payment'
    )
    reference_code = models.CharField(max_length=50, unique=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)  # 102.5% of bid amount
    startup_amount = models.DecimalField(max_digits=10, decimal_places=2)  # 97.5% of bid amount
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2)  # 5% fee
    enterprise_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=2.50)
    startup_fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=2.50)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    instructions_sent_at = models.DateTimeField(null=True, blank=True)
    payment_initiated_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    
    # Wire transfer details provided by enterprise
    wire_transfer_date = models.DateField(null=True, blank=True)
    wire_transfer_confirmation = models.CharField(max_length=255, null=True, blank=True)
    
    # Bank account details for startup payment
    startup_bank_name = models.CharField(max_length=255, null=True, blank=True)
    startup_account_number = models.CharField(max_length=255, null=True, blank=True)
    startup_routing_number = models.CharField(max_length=255, null=True, blank=True)
    
    # Admin notes
    admin_notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Escrow Payment for Bid #{self.pilot_bid.id} - ${self.total_amount}"
    
    def generate_reference_code(self):
        """Generate a unique reference code for this payment"""
        prefix = "FND-PILOT"
        bid_id = self.pilot_bid.id
        timestamp = int(self.created_at.timestamp())
        return f"{prefix}-{bid_id}-{timestamp}"
    
    def save(self, *args, **kwargs):
        # Generate reference code if this is a new record
        if not self.pk and not self.reference_code:
            # Temporarily save to get an ID and timestamp
            super().save(*args, **kwargs)
            self.reference_code = self.generate_reference_code()
            
        # Now save again with the reference code
            return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)
    
    def mark_as_instructions_sent(self):
        """Mark payment instructions as sent to enterprise"""
        self.status = 'instructions_sent'
        self.instructions_sent_at = timezone.now()
        self.save(update_fields=['status', 'instructions_sent_at'])
    
    def mark_as_payment_initiated(self, wire_date=None, confirmation=None):
        """Enterprise marks payment as initiated"""
        self.status = 'payment_initiated'
        self.payment_initiated_at = timezone.now()
        if wire_date:
            self.wire_transfer_date = wire_date
        if confirmation:
            self.wire_transfer_confirmation = confirmation
        self.save(update_fields=['status', 'payment_initiated_at', 
                                 'wire_transfer_date', 'wire_transfer_confirmation'])
        
        # Create notification for admin
        self.create_admin_notification("Payment Initiated", 
                                       f"Enterprise has initiated payment of ${self.total_amount} for pilot '{self.pilot_bid.pilot.title}'.")
        
        # Create notification for startup
        self.create_startup_notification("Payment In Process", 
                                        f"Enterprise has initiated payment for your approved bid on pilot '{self.pilot_bid.pilot.title}'.")
    
    def mark_as_received(self):
        """Admin marks payment as received"""
        self.status = 'received'
        self.received_at = timezone.now()
        self.save(update_fields=['status', 'received_at'])
        
        # Create notifications
        self.create_enterprise_notification("Payment Received", 
                                           f"Your payment of ${self.total_amount} for pilot '{self.pilot_bid.pilot.title}' has been received.")
        
        self.create_startup_notification("Payment Received", 
                                        f"Payment for your bid on pilot '{self.pilot_bid.pilot.title}' has been received and is held in escrow.")
    
    def mark_as_approved(self):
        """Mark the bid as approved and create escrow payment"""
        if self.status != 'pending' and self.status != 'under_review':
            return False
        
        # Update bid status
        self.status = 'approved'
        self.save(update_fields=['status'])
        
        # Calculate payment amounts
        total_fee_percentage = self.enterprise_fee_percentage + self.startup_fee_percentage
        total_fee_amount = (self.amount * total_fee_percentage) / 100
        platform_fee = total_fee_amount
        total_amount = self.amount + (self.amount * self.enterprise_fee_percentage / 100)  # 102.5%
        startup_amount = self.amount  # 100%
        
        # Create escrow payment
        from apps.payments.models import EscrowPayment
        escrow_payment = EscrowPayment.objects.create(
            pilot_bid=self,
            total_amount=total_amount,
            startup_amount=startup_amount,
            platform_fee=platform_fee,
            enterprise_fee_percentage=self.enterprise_fee_percentage,
            startup_fee_percentage=self.startup_fee_percentage
        )
        
        # Mark payment instructions as sent
        escrow_payment.mark_as_instructions_sent()
        
        return escrow_payment
    
    def mark_as_released(self):
        """Admin marks payment as released to startup"""
        self.status = 'released'
        self.released_at = timezone.now()
        self.save(update_fields=['status', 'released_at'])
        
        # Update pilot bid status if not already updated
        if self.pilot_bid.status != 'paid':
            self.pilot_bid.status = 'paid'
            self.pilot_bid.save(update_fields=['status'])
        
        # Create notifications
        self.create_enterprise_notification("Payment Completed", 
                                        f"Your payment for pilot '{self.pilot_bid.pilot.title}' has been disbursed to the startup.")
        
        self.create_startup_notification("Payment Released", 
                                        f"Payment of ${self.startup_amount} for pilot '{self.pilot_bid.pilot.title}' has been released to your account.")
    
    def create_enterprise_notification(self, title, message):
        """Create notification for the enterprise"""
        from apps.notifications.services import create_bid_notification
        return create_bid_notification(
            bid=self.pilot_bid,
            notification_type='payment_received',
            title=title,
            message=message
        )
    
    def create_startup_notification(self, title, message):
        """Create notification for the startup"""
        from apps.notifications.services import create_bid_notification
        return create_bid_notification(
            bid=self.pilot_bid,
            notification_type='payment_received',
            title=title,
            message=message
        )
    
    def create_admin_notification(self, title, message):
        """Create notification for admin users"""
        from apps.notifications.services import create_notification
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get admin users
        admins = User.objects.filter(is_staff=True)
        
        notifications = []
        for admin in admins:
            notification = create_notification(
                recipient=admin,
                notification_type='payment_received',
                title=title,
                message=message,
                related_pilot=self.pilot_bid.pilot,
                related_bid=self.pilot_bid
            )
            notifications.append(notification)
        
        return notifications


class EscrowPaymentLog(models.Model):
    """Audit log for escrow payment status changes"""
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
        return f"Payment {self.escrow_payment.reference_code} status changed from {self.previous_status} to {self.new_status}"