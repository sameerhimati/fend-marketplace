from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from django.core.files.storage import default_storage
import os
from .models import Organization


@receiver(post_delete, sender=Organization)
def delete_organization_files(sender, instance, **kwargs):
    """Delete associated files when an Organization is deleted"""
    if instance.logo and instance.logo.name:
        try:
            if default_storage.exists(instance.logo.name):
                default_storage.delete(instance.logo.name)
                print(f"Deleted organization logo: {instance.logo.name}")
        except Exception as e:
            print(f"Error deleting organization logo {instance.logo.name}: {e}")


@receiver(pre_save, sender=Organization)
def delete_old_organization_files(sender, instance, **kwargs):
    """Delete old logo when new one is uploaded"""
    if not instance.pk:
        return  # New instance, no old files to delete
    
    try:
        old_instance = Organization.objects.get(pk=instance.pk)
        
        # Check if logo has changed
        if (old_instance.logo and old_instance.logo.name and 
            instance.logo != old_instance.logo):
            try:
                if default_storage.exists(old_instance.logo.name):
                    default_storage.delete(old_instance.logo.name)
                    print(f"Deleted old organization logo: {old_instance.logo.name}")
            except Exception as e:
                print(f"Error deleting old organization logo {old_instance.logo.name}: {e}")
                
    except Organization.DoesNotExist:
        pass  # Original instance doesn't exist