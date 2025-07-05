from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import secrets
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

class User(AbstractUser):
    organization = models.ForeignKey(
        'organizations.Organization', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=False,
        related_name='users'
    )
    
    # Track if user needs to change password on next login
    must_change_password = models.BooleanField(
        default=False,
        help_text="If true, user will be forced to change password on next login"
    )
    
    # Track last password change
    password_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time the user changed their password"
    )

    def clean(self):
        super().clean()
        # Only enforce for non-superusers
        if not self.is_superuser and not self.organization:
            from django.core.exceptions import ValidationError
            raise ValidationError({'organization': 'Users must be associated with an organization'})
    
    def __str__(self):
        return self.username or self.email


class PasswordReset(models.Model):
    """Track password resets initiated by admin"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='password_resets'
    )
    admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='initiated_resets',
        help_text="Admin who initiated the reset"
    )
    temporary_password = models.CharField(
        max_length=50,
        help_text="Temporary password (stored for record keeping only)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the user first logged in with temp password"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this password reset is still valid/active"
    )
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Password reset for {self.user} on {self.created_at}"


class PasswordResetRequest(models.Model):
    """Model to track forgot password requests from users"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    email = models.EmailField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="User found with this email (if exists)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Admin handling
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handled_password_requests',
        help_text="Admin who handled this request"
    )
    handled_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(
        blank=True,
        help_text="Admin notes about this request"
    )
    
    class Meta:
        ordering = ['-requested_at']
        verbose_name = "Password Reset Request"
        verbose_name_plural = "Password Reset Requests"
    
    def __str__(self):
        return f"Password reset request for {self.email} - {self.status}"
    
    @property
    def is_pending(self):
        return self.status == 'pending'
    
    @property
    def user_exists(self):
        return self.user is not None


