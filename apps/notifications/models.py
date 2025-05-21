from django.db import models

class Notification(models.Model):
    TYPES = [
        ('bid_submitted', 'New Bid Submitted'),
        ('bid_updated', 'Bid Status Updated'),
        ('pilot_updated', 'Pilot Updated'),
        ('payment_received', 'Payment Received'),
        ('pilot_pending_approval', 'Pilot Pending Approval'),
        ('admin_pilot_verification', 'Admin Pilot Verification'),
        ('pilot_approved', 'Pilot Approved'),
        ('pilot_rejected', 'Pilot Rejected'),
        ('bid_live', 'Bid Live'),
    ]

    recipient = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=25, choices=TYPES)
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