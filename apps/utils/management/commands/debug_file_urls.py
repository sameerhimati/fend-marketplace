from django.core.management.base import BaseCommand
from django.conf import settings
from apps.pilots.models import Pilot, PilotBid
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = 'Debug file URLs and storage to understand how uploads are organized'

    def handle(self, *args, **options):
        self.stdout.write("=== File Upload Organization Debug ===\n")
        
        # Show Django settings
        self.stdout.write("Django Storage Settings:")
        self.stdout.write(f"  USE_S3: {getattr(settings, 'USE_S3', 'Not set')}")
        self.stdout.write(f"  DEFAULT_FILE_STORAGE: {getattr(settings, 'DEFAULT_FILE_STORAGE', 'Default Django')}")
        self.stdout.write(f"  MEDIA_URL: {getattr(settings, 'MEDIA_URL', 'Not set')}")
        self.stdout.write(f"  MEDIA_ROOT: {getattr(settings, 'MEDIA_ROOT', 'Not set')}")
        self.stdout.write(f"  AWS_S3_CUSTOM_DOMAIN: {getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', 'Not set')}")
        self.stdout.write("")

        # Check pilot files
        self.stdout.write("=== Pilot Document Analysis ===")
        for pilot in Pilot.objects.all()[:3]:  # Just check first 3
            self.stdout.write(f"Pilot {pilot.id}: {pilot.title}")
            
            files_to_check = [
                ('Technical Specs', pilot.technical_specs_doc),
                ('Performance Metrics', pilot.performance_metrics_doc),
                ('Compliance', pilot.compliance_requirements_doc),
            ]
            
            for doc_type, file_field in files_to_check:
                if file_field:
                    try:
                        self.stdout.write(f"  {doc_type}:")
                        self.stdout.write(f"    File name: {file_field.name}")
                        self.stdout.write(f"    File URL: {file_field.url}")
                        self.stdout.write(f"    Storage class: {type(file_field.storage).__name__}")
                        
                        # Check if file exists locally
                        import os
                        local_path = f"/app/media/{file_field.name}"
                        if os.path.exists(local_path):
                            self.stdout.write(f"    Local file: EXISTS ({os.path.getsize(local_path)} bytes)")
                        else:
                            self.stdout.write(f"    Local file: NOT FOUND")
                            
                    except Exception as e:
                        self.stdout.write(f"    ERROR: {e}")
                else:
                    self.stdout.write(f"  {doc_type}: No file uploaded")
            self.stdout.write("")

        # Check organization logos
        self.stdout.write("=== Organization Logo Analysis ===")
        for org in Organization.objects.filter(logo__isnull=False)[:3]:
            self.stdout.write(f"Org: {org.name}")
            try:
                self.stdout.write(f"  Logo name: {org.logo.name}")
                self.stdout.write(f"  Logo URL: {org.logo.url}")
                self.stdout.write(f"  Storage class: {type(org.logo.storage).__name__}")
                
                # Check if file exists locally
                import os
                local_path = f"/app/media/{org.logo.name}"
                if os.path.exists(local_path):
                    self.stdout.write(f"  Local file: EXISTS ({os.path.getsize(local_path)} bytes)")
                else:
                    self.stdout.write(f"  Local file: NOT FOUND")
                    
            except Exception as e:
                self.stdout.write(f"  ERROR: {e}")
            self.stdout.write("")

        # Show current file organization
        self.stdout.write("=== Current Media Directory Structure ===")
        import os
        media_root = "/app/media"
        if os.path.exists(media_root):
            for root, dirs, files in os.walk(media_root):
                level = root.replace(media_root, '').count(os.sep)
                indent = ' ' * 2 * level
                self.stdout.write(f"{indent}{os.path.basename(root)}/")
                subindent = ' ' * 2 * (level + 1)
                for file in files[:3]:  # Limit to first 3 files per directory
                    size = os.path.getsize(os.path.join(root, file))
                    self.stdout.write(f"{subindent}{file} ({size} bytes)")
                if len(files) > 3:
                    self.stdout.write(f"{subindent}... and {len(files) - 3} more files")
        else:
            self.stdout.write("Media directory does not exist")

        self.stdout.write("\n=== Summary ===")
        self.stdout.write("This shows how your files are currently organized and where URLs point to.")
        self.stdout.write("If you see AccessDenied errors, it means the URL points to Spaces but the file isn't there.")