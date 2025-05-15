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
    is_verified = models.BooleanField(default=False)
    
    def __str__(self):
        return self.username or self.email

class EmailVerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verification_tokens')
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)
    
    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(hours=24)
    
    @classmethod
    def generate_token(cls, user):
        """Generate a unique verification token for a user"""
        token = secrets.token_urlsafe(32)
        return cls.objects.create(user=user, token=token)

    
    def __str__(self):
        return f"Token for {self.user.email}"

@receiver(post_save, sender=User)
def auto_verify_admin_users(sender, instance, created, **kwargs):
    """Automatically mark staff/superuser accounts as verified"""
    if created and (instance.is_staff or instance.is_superuser):
        instance.is_verified = True
        instance.save(update_fields=['is_verified'])