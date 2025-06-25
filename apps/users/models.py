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

    def clean(self):
        super().clean()
        # Only enforce for non-superusers
        if not self.is_superuser and not self.organization:
            from django.core.exceptions import ValidationError
            raise ValidationError({'organization': 'Users must be associated with an organization'})
    
    def __str__(self):
        return self.username or self.email


