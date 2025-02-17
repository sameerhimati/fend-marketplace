from django.db import models

class Organization(models.Model):
    ORGANIZATION_TYPES = (
        ('enterprise', 'Enterprise'),
        ('startup', 'Startup'),
    )

    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=ORGANIZATION_TYPES)
    domain = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name