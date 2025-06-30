import os
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Collect static files and ensure they are uploaded to S3/Spaces'

    def add_arguments(self, parser):
        parser.add_argument(
            '--noinput',
            action='store_true',
            help='Do not prompt for input',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing files before collecting',
        )

    def handle(self, *args, **options):
        # First run normal collectstatic
        self.stdout.write('Running collectstatic...')
        call_command('collectstatic', 
                    interactive=not options.get('noinput', False),
                    clear=options.get('clear', False))
        
        # If using S3, verify and upload CSS files
        if getattr(settings, 'USE_S3', False):
            self.stdout.write(
                self.style.SUCCESS('\nVerifying S3 uploads...')
            )
            
            from fend.storage_backends import StaticStorage
            from django.core.files.base import File
            import os
            
            storage = StaticStorage()
            
            # Verify ALL static files are uploaded to S3
            static_dirs = [
                '/app/staticfiles',  # Where collectstatic puts files
                '/app/static',       # Source static files
            ]
            
            missing_files = []
            verified_files = 0
            
            for static_dir in static_dirs:
                if os.path.exists(static_dir):
                    self.stdout.write(f'\nChecking {static_dir}...')
                    
                    for root, dirs, files in os.walk(static_dir):
                        for filename in files:
                            filepath = os.path.join(root, filename)
                            
                            # Calculate S3 path relative to static directory
                            rel_path = os.path.relpath(filepath, static_dir)
                            s3_path = rel_path.replace('\\', '/')  # Handle Windows paths
                            
                            # Skip hidden files and Python cache
                            if filename.startswith('.') or '__pycache__' in filepath:
                                continue
                            
                            # Check if file exists in S3
                            if not storage.exists(s3_path):
                                missing_files.append((filepath, s3_path))
                            else:
                                verified_files += 1
            
            # Upload any missing files
            if missing_files:
                self.stdout.write(
                    self.style.WARNING(f'\nFound {len(missing_files)} missing files in S3. Uploading...')
                )
                
                for filepath, s3_path in missing_files:
                    try:
                        with open(filepath, 'rb') as f:
                            storage.save(s3_path, File(f))
                            self.stdout.write(f'  ✓ Uploaded: {s3_path}')
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'  ✗ Failed to upload {s3_path}: {e}')
                        )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Static files sync complete! '
                    f'Verified: {verified_files}, Uploaded: {len(missing_files)}'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('\n✅ Static files collected (local storage)')
            )