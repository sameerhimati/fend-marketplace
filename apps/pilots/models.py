# apps/pilots/models.py
from django.db import models
from apps.organizations.models import Organization, PilotDefinition

class Pilot(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    # Link to the organization creating the pilot
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='pilots'
    )
    
    # Link to the organization's pilot definition template
    pilot_definition = models.ForeignKey(
        PilotDefinition,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_pilots'
    )

    # Pilot specific fields
    title = models.CharField(max_length=255)
    description = models.TextField()
    requirements = models.JSONField(default=list)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    
    # Auto-populated from PilotDefinition but can be overridden
    technical_specs_doc = models.FileField(
        upload_to='pilot_specs/',
        null=True,
        blank=True
    )
    performance_metrics = models.TextField(null=True, blank=True)
    compliance_requirements = models.TextField(null=True, blank=True)
    is_private = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # If this is a new pilot and has a pilot definition
        if not self.pk and self.pilot_definition:
            # Pre-populate fields from the organization's pilot definition
            self.technical_specs_doc = self.pilot_definition.technical_specs_doc
            self.performance_metrics = self.pilot_definition.performance_metrics
            self.compliance_requirements = self.pilot_definition.compliance_requirements
            self.is_private = self.pilot_definition.is_private
        super().save(*args, **kwargs)
    
    def is_editable(self):
        """Check if pilot can be edited"""
        return self.status in ['draft', 'published']

    def is_viewable_by(self, user):
        """Check if a user can view this pilot"""
        if user.is_superuser:
            return True
        
        user_org = user.organization
        if user_org.type == 'enterprise':
            return self.organization == user_org
        elif user_org.type == 'startup':
            return (not self.is_private and self.status == 'published')
        return False

    def can_be_edited_by(self, user):
        """Check if a user can edit this pilot"""
        if user.is_superuser:
            return True
            
        user_org = user.organization
        if user_org.type == 'enterprise':
            return self.organization == user_org and self.is_editable()
        return False

    def get_formatted_requirements(self):
        """Return requirements in a formatted way"""
        if not self.requirements:
            return []
        
        formatted = []
        for req in self.requirements:
            if isinstance(req, dict):
                req_type = req.get('type', 'text')
                content = req.get('content', '')
                formatted.append({
                    'type': req_type,
                    'content': content
                })
        return formatted