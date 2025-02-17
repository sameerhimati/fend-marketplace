from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members'
    )
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.email