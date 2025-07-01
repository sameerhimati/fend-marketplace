from django.db import models

class Notification(models.Model):
    TYPES = [
        ('bid_submitted', 'New Bid Submitted'),
        ('bid_under_review', 'Bid Under Review'),
        ('bid_approved', 'Bid Approved'),
        ('bid_live', 'Bid Live - Work Started'),
        ('bid_declined', 'Bid Declined'),
        ('bid_withdrawn', 'Bid Withdrawn'),
        ('completion_requested', 'Completion Requested'),
        ('completion_verified', 'Completion Verified'),
        ('work_completed', 'Work Completed'),
        ('pilot_pending_approval', 'Pilot Pending Approval'),
        ('pilot_approved', 'Pilot Approved'),
        ('pilot_rejected', 'Pilot Rejected'),
        ('pilot_updated', 'Pilot Updated'),
        ('payment_received', 'Payment Received'),
        ('payment_verification_needed', 'Payment Verification Needed'),
        ('payment_failed', 'Payment Failed'),
        ('subscription_expiring_soon', 'Subscription Expiring Soon'),
        ('subscription_expired', 'Subscription Expired'),
        ('subscription_renewed', 'Subscription Renewed'),
        ('deal_expiring_soon', 'Deal Expiring Soon'),
        ('monthly_deals_digest', 'Monthly Deals Digest'),
        ('admin_pilot_verification', 'Admin Pilot Verification'),
        ('admin_action_required', 'Admin Action Required'),
        ('account_approved', 'Account Approved'),
    ]

    recipient = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=50, choices=TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    related_pilot = models.ForeignKey('pilots.Pilot', on_delete=models.CASCADE, null=True, blank=True)
    related_bid = models.ForeignKey('pilots.PilotBid', on_delete=models.CASCADE, null=True, blank=True)

class NotificationPreferences(models.Model):
    user = models.OneToOneField('users.User', on_delete=models.CASCADE, related_name='notification_preferences')
    enabled = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.email} - {'Enabled' if self.enabled else 'Disabled'}"