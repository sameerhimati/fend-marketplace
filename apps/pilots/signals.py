from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from django.core.files.storage import default_storage
import os
from .models import Pilot, PilotBid


@receiver(post_delete, sender=Pilot)
def delete_pilot_files(sender, instance, **kwargs):
    """Delete associated files when a Pilot is deleted"""
    files_to_delete = [
        instance.technical_specs_doc,
        instance.performance_metrics_doc,
        instance.compliance_requirements_doc,
    ]
    
    for file_field in files_to_delete:
        if file_field and file_field.name:
            try:
                if default_storage.exists(file_field.name):
                    default_storage.delete(file_field.name)
                    print(f"Deleted file: {file_field.name}")
            except Exception as e:
                print(f"Error deleting file {file_field.name}: {e}")


@receiver(post_delete, sender=PilotBid)
def delete_bid_files(sender, instance, **kwargs):
    """Delete associated files when a PilotBid is deleted"""
    if instance.proposal_doc and instance.proposal_doc.name:
        try:
            if default_storage.exists(instance.proposal_doc.name):
                default_storage.delete(instance.proposal_doc.name)
                print(f"Deleted bid file: {instance.proposal_doc.name}")
        except Exception as e:
            print(f"Error deleting bid file {instance.proposal_doc.name}: {e}")


@receiver(pre_save, sender=Pilot)
def delete_old_pilot_files(sender, instance, **kwargs):
    """Delete old files when new ones are uploaded"""
    if not instance.pk:
        return  # New instance, no old files to delete
    
    try:
        old_instance = Pilot.objects.get(pk=instance.pk)
        
        # Check each file field for changes
        file_fields = [
            ('technical_specs_doc', old_instance.technical_specs_doc),
            ('performance_metrics_doc', old_instance.performance_metrics_doc), 
            ('compliance_requirements_doc', old_instance.compliance_requirements_doc),
        ]
        
        for field_name, old_file in file_fields:
            new_file = getattr(instance, field_name)
            
            # If file has changed and old file exists, delete it
            if old_file and old_file.name and new_file != old_file:
                try:
                    if default_storage.exists(old_file.name):
                        default_storage.delete(old_file.name)
                        print(f"Deleted old file: {old_file.name}")
                except Exception as e:
                    print(f"Error deleting old file {old_file.name}: {e}")
                    
    except Pilot.DoesNotExist:
        pass  # Original instance doesn't exist


@receiver(pre_save, sender=PilotBid)
def delete_old_bid_files(sender, instance, **kwargs):
    """Delete old proposal documents when new ones are uploaded"""
    if not instance.pk:
        return  # New instance, no old files to delete
    
    try:
        old_instance = PilotBid.objects.get(pk=instance.pk)
        
        # Check if proposal document has changed
        if (old_instance.proposal_doc and old_instance.proposal_doc.name and 
            instance.proposal_doc != old_instance.proposal_doc):
            try:
                if default_storage.exists(old_instance.proposal_doc.name):
                    default_storage.delete(old_instance.proposal_doc.name)
                    print(f"Deleted old bid file: {old_instance.proposal_doc.name}")
            except Exception as e:
                print(f"Error deleting old bid file {old_instance.proposal_doc.name}: {e}")
                
    except PilotBid.DoesNotExist:
        pass  # Original instance doesn't exist