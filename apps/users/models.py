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
    is_verified = models.BooleanField(default=True)

    def clean(self):
        super().clean()
        # Only enforce for non-superusers
        if not self.is_superuser and not self.organization:
            from django.core.exceptions import ValidationError
            raise ValidationError({'organization': 'Users must be associated with an organization'})
    
    def __str__(self):
        return self.username or self.email

@receiver(post_save, sender=User)
def auto_verify_admin_users(sender, instance, created, **kwargs):
    """Automatically mark staff/superuser accounts as verified"""
    if created and (instance.is_staff or instance.is_superuser):
        instance.is_verified = True
        instance.save(update_fields=['is_verified'])

# @receiver(pre_save, sender=User)
# def ensure_user_has_organization(sender, instance, **kwargs):
#     """Ensure that users always have an organization."""
#     if not instance.is_superuser and not instance.organization:
#         # Find existing organization from same email domain
#         email_domain = instance.email.split('@')[-1] if instance.email else None
        
#         if email_domain:
#             # Try to find an existing organization with same email domain
#             from apps.organizations.models import Organization
#             existing_users = User.objects.filter(
#                 email__endswith=f"@{email_domain}",
#                 organization__isnull=False
#             )
            
#             if existing_users.exists():
#                 # Use the same organization as other users from this domain
#                 instance.organization = existing_users.first().organization
#                 return
        
#         # Create a default organization if needed
#         from apps.organizations.models import Organization
#         from django.utils import timezone
        
#         # Create a minimal organization for the user
#         org_name = f"{instance.username}'s Organization"
#         if instance.first_name and instance.last_name:
#             org_name = f"{instance.first_name} {instance.last_name}'s Organization"
        
#         org_type = 'enterprise' if instance.is_staff else 'startup'
        
#         org = Organization.objects.create(
#             name=org_name,
#             type=org_type,
#             website=f"example.com/{instance.username}",
#             primary_contact_name=f"{instance.first_name} {instance.last_name}".strip() or instance.username,
#             primary_contact_phone="0000000000",
#             country_code="+1",
#             approval_status='approved',
#             onboarding_completed=True,
#             created_at=timezone.now(),
#             updated_at=timezone.now()
#         )
        
#         instance.organization = org