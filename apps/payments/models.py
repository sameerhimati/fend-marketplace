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