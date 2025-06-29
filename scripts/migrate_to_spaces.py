#!/usr/bin/env python
"""
Migration script to transfer existing media files from local storage to Digital Ocean Spaces.
Run this after deploying the new storage configuration.
"""
import os
import sys
import django
from pathlib import Path

# Add the project root to Python path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fend.settings.production')
django.setup()

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from apps.organizations.models import Organization
from apps.pilots.models import Pilot, PilotBid


def migrate_organization_logos():
    """Migrate organization logos to DO Spaces"""
    print("Migrating organization logos...")
    
    for org in Organization.objects.filter(logo__isnull=False):
        if org.logo and hasattr(org.logo, 'file'):
            try:
                # Read the existing file
                with org.logo.open('rb') as f:
                    content = f.read()
                
                # Create new path for DO Spaces
                old_path = org.logo.name
                new_path = f"logos/{os.path.basename(old_path)}"
                
                # Save to DO Spaces
                content_file = ContentFile(content)
                saved_path = default_storage.save(new_path, content_file)
                
                # Update the model
                org.logo.name = saved_path
                org.save(update_fields=['logo'])
                
                print(f"✓ Migrated logo for {org.name}: {old_path} -> {saved_path}")
                
            except Exception as e:
                print(f"✗ Failed to migrate logo for {org.name}: {e}")


def migrate_pilot_documents():
    """Migrate pilot documents to DO Spaces"""
    print("Migrating pilot documents...")
    
    # Technical specs
    for pilot in Pilot.objects.filter(technical_specs_doc__isnull=False):
        migrate_pilot_file(pilot, 'technical_specs_doc', 'technical')
    
    # Performance metrics
    for pilot in Pilot.objects.filter(performance_metrics_doc__isnull=False):
        migrate_pilot_file(pilot, 'performance_metrics_doc', 'performance')
    
    # Compliance requirements
    for pilot in Pilot.objects.filter(compliance_requirements_doc__isnull=False):
        migrate_pilot_file(pilot, 'compliance_requirements_doc', 'compliance')


def migrate_pilot_file(pilot, field_name, doc_type):
    """Migrate a single pilot document file"""
    try:
        file_field = getattr(pilot, field_name)
        if file_field and hasattr(file_field, 'file'):
            with file_field.open('rb') as f:
                content = f.read()
            
            old_path = file_field.name
            filename = os.path.basename(old_path)
            org_slug = pilot.organization.name.lower().replace(' ', '-')
            new_path = f"documents/pilots/{org_slug}/{pilot.pk}/{doc_type}/{filename}"
            
            content_file = ContentFile(content)
            saved_path = default_storage.save(new_path, content_file)
            
            setattr(pilot, field_name, saved_path)
            pilot.save(update_fields=[field_name])
            
            print(f"✓ Migrated {doc_type} doc for pilot {pilot.title}: {old_path} -> {saved_path}")
            
    except Exception as e:
        print(f"✗ Failed to migrate {doc_type} doc for pilot {pilot.title}: {e}")


def migrate_bid_documents():
    """Migrate pilot bid documents to DO Spaces"""
    print("Migrating pilot bid documents...")
    
    for bid in PilotBid.objects.filter(proposal_doc__isnull=False):
        try:
            if bid.proposal_doc and hasattr(bid.proposal_doc, 'file'):
                with bid.proposal_doc.open('rb') as f:
                    content = f.read()
                
                old_path = bid.proposal_doc.name
                filename = os.path.basename(old_path)
                startup_slug = bid.startup.name.lower().replace(' ', '-')
                pilot_slug = bid.pilot.title.lower().replace(' ', '-')
                new_path = f"documents/bids/{startup_slug}/{pilot_slug}/{filename}"
                
                content_file = ContentFile(content)
                saved_path = default_storage.save(new_path, content_file)
                
                bid.proposal_doc.name = saved_path
                bid.save(update_fields=['proposal_doc'])
                
                print(f"✓ Migrated bid doc for {bid.startup.name}: {old_path} -> {saved_path}")
                
        except Exception as e:
            print(f"✗ Failed to migrate bid doc for {bid.startup.name}: {e}")


def main():
    print("Starting migration to Digital Ocean Spaces...")
    print("=" * 50)
    
    # Check if USE_S3 is enabled
    from django.conf import settings
    if not getattr(settings, 'USE_S3', False):
        print("ERROR: USE_S3 is not enabled in settings.")
        print("Please ensure production settings are loaded and USE_S3=True")
        return
    
    try:
        # Test connection first
        test_file = ContentFile(b'Migration test')
        test_path = default_storage.save('test/migration_test.txt', test_file)
        default_storage.delete(test_path)
        print("✓ Connection to Digital Ocean Spaces verified")
        
    except Exception as e:
        print(f"✗ Failed to connect to Digital Ocean Spaces: {e}")
        return
    
    # Run migrations
    migrate_organization_logos()
    migrate_pilot_documents()
    migrate_bid_documents()
    
    print("=" * 50)
    print("Migration completed!")
    print("\nNext steps:")
    print("1. Verify files are accessible via CDN URLs")
    print("2. Test file uploads through the Django admin")
    print("3. Run: python manage.py collectstatic --noinput")
    print("4. Remove old local media files after verification")


if __name__ == '__main__':
    main()