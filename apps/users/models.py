from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta
import secrets
from django.db.models.signals import post_save
from django.dispatch import receiver

class User(AbstractUser):
    organization = models.ForeignKey(
        'organizations.Organization', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='users'
    )
    is_verified = models.BooleanField(default=True)
    
    def __str__(self):
        return self.username or self.email

@receiver(post_save, sender=User)
def auto_verify_admin_users(sender, instance, created, **kwargs):
    """Automatically mark staff/superuser accounts as verified"""
    if created and (instance.is_staff or instance.is_superuser):
        instance.is_verified = True
        instance.save(update_fields=['is_verified'])