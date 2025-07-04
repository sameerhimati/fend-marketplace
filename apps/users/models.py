from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
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
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Password reset for {self.user} on {self.created_at}"


