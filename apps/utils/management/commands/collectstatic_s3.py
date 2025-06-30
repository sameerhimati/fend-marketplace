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
            
            # Check and upload CSS files
            css_dirs = [
                ('/app/static/css', 'css'),
                ('/app/staticfiles/css', 'css'),
            ]
            
            for local_dir, s3_prefix in css_dirs:
                if os.path.exists(local_dir):
                    self.stdout.write(f'\nChecking {local_dir}...')
                    for filename in os.listdir(local_dir):
                        if filename.endswith('.css'):
                            filepath = os.path.join(local_dir, filename)
                            s3_path = f'{s3_prefix}/{filename}'
                            
                            # Check if file exists in S3
                            if not storage.exists(s3_path):
                                self.stdout.write(f'  Uploading missing file: {s3_path}')
                                with open(filepath, 'rb') as f:
                                    storage.save(s3_path, File(f))
                            else:
                                self.stdout.write(f'  ✓ {s3_path} already exists')
            
            # Also check admin CSS
            admin_css_dir = '/usr/local/lib/python3.11/site-packages/django/contrib/admin/static/admin/css'
            if os.path.exists(admin_css_dir):
                self.stdout.write(f'\nChecking admin CSS...')
                for filename in os.listdir(admin_css_dir):
                    if filename.endswith('.css'):
                        filepath = os.path.join(admin_css_dir, filename)
                        s3_path = f'admin/css/{filename}'
                        
                        if not storage.exists(s3_path):
                            self.stdout.write(f'  Uploading missing file: {s3_path}')
                            with open(filepath, 'rb') as f:
                                storage.save(s3_path, File(f))
            
            self.stdout.write(
                self.style.SUCCESS('\n✅ All CSS files verified in S3!')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('\n✅ Static files collected (local storage)')
            )