from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from django.conf import settings
from apps.pilots.models import Pilot, PilotBid
from apps.organizations.models import Organization
import os
from datetime import datetime, timedelta


class Command(BaseCommand):
    help = 'Clean up orphaned files that are no longer referenced by any model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what files would be deleted without actually deleting them',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Only delete files older than this many days (default: 7)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        days_old = options['days']
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        self.stdout.write(f"Looking for orphaned files older than {days_old} days...")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No files will be deleted"))
        
        # Get all file paths referenced in the database
        referenced_files = set()
        
        # Pilot files
        for pilot in Pilot.objects.all():
            if pilot.technical_specs_doc:
                referenced_files.add(pilot.technical_specs_doc.name)
            if pilot.performance_metrics_doc:
                referenced_files.add(pilot.performance_metrics_doc.name)
            if pilot.compliance_requirements_doc:
                referenced_files.add(pilot.compliance_requirements_doc.name)
        
        # Bid files
        for bid in PilotBid.objects.all():
            if bid.proposal_doc:
                referenced_files.add(bid.proposal_doc.name)
        
        # Organization logos
        for org in Organization.objects.all():
            if org.logo:
                referenced_files.add(org.logo.name)
        
        self.stdout.write(f"Found {len(referenced_files)} files referenced in database")
        
        # List all files in storage directories
        directories_to_check = [
            'documents/pilots/',
            'documents/bids/',
            'logos/',
            'media/',  # Include general media directory
        ]
        
        orphaned_files = []
        total_files_checked = 0
        
        for directory in directories_to_check:
            try:
                dirs, files = default_storage.listdir(directory)
                
                # Recursively check subdirectories
                def check_directory(path):
                    nonlocal total_files_checked
                    try:
                        dirs, files = default_storage.listdir(path)
                        
                        for file in files:
                            file_path = os.path.join(path, file)
                            total_files_checked += 1
                            
                            # Check if file is referenced in database
                            if file_path not in referenced_files:
                                try:
                                    # Check file age if possible
                                    file_info = default_storage.get_created_time(file_path)
                                    if file_info < cutoff_date:
                                        orphaned_files.append(file_path)
                                except:
                                    # If we can't get file date, consider it for deletion
                                    orphaned_files.append(file_path)
                        
                        # Recursively check subdirectories
                        for subdir in dirs:
                            check_directory(os.path.join(path, subdir))
                            
                    except Exception as e:
                        self.stdout.write(f"Error checking directory {path}: {e}")
                
                check_directory(directory)
                
            except Exception as e:
                self.stdout.write(f"Directory {directory} not found or error: {e}")
        
        self.stdout.write(f"Checked {total_files_checked} files total")
        self.stdout.write(f"Found {len(orphaned_files)} orphaned files")
        
        if not orphaned_files:
            self.stdout.write(self.style.SUCCESS("No orphaned files found!"))
            return
        
        # Show orphaned files
        for file_path in orphaned_files:
            if dry_run:
                self.stdout.write(f"Would delete: {file_path}")
            else:
                try:
                    default_storage.delete(file_path)
                    self.stdout.write(f"Deleted: {file_path}")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error deleting {file_path}: {e}"))
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: {len(orphaned_files)} files would be deleted. "
                    "Run without --dry-run to actually delete them."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully cleaned up {len(orphaned_files)} orphaned files"
                )
            )