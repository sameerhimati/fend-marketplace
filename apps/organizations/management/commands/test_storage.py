from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings
import io


class Command(BaseCommand):
    help = 'Test Digital Ocean Spaces storage configuration'

    def handle(self, *args, **options):
        self.stdout.write('Testing Digital Ocean Spaces configuration...')
        
        # Check if USE_S3 is enabled
        use_s3 = getattr(settings, 'USE_S3', False)
        self.stdout.write(f'USE_S3 setting: {use_s3}')
        
        if not use_s3:
            self.stdout.write(
                self.style.WARNING('USE_S3 is False. Using local storage.')
            )
            return
        
        # Test basic storage connection
        try:
            # Create a test file
            test_content = ContentFile(b'This is a test file for DO Spaces')
            test_filename = 'test/storage_test.txt'
            
            # Upload test file
            self.stdout.write('Uploading test file...')
            saved_name = default_storage.save(test_filename, test_content)
            self.stdout.write(f'File saved as: {saved_name}')
            
            # Get file URL
            file_url = default_storage.url(saved_name)
            self.stdout.write(f'File URL: {file_url}')
            
            # Check if file exists
            exists = default_storage.exists(saved_name)
            self.stdout.write(f'File exists: {exists}')
            
            # Read file back
            if exists:
                with default_storage.open(saved_name, 'rb') as f:
                    content = f.read()
                    self.stdout.write(f'File content: {content.decode()}')
            
            # Clean up - delete test file
            default_storage.delete(saved_name)
            self.stdout.write('Test file deleted')
            
            self.stdout.write(
                self.style.SUCCESS('✓ Digital Ocean Spaces storage test completed successfully!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Storage test failed: {str(e)}')
            )
            
            # Display configuration for debugging
            self.stdout.write('\nCurrent configuration:')
            for key in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_STORAGE_BUCKET_NAME', 
                       'AWS_S3_ENDPOINT_URL', 'AWS_S3_REGION_NAME']:
                value = getattr(settings, key, 'Not set')
                # Mask sensitive values
                if 'SECRET' in key or 'KEY' in key:
                    value = f'{value[:4]}...{value[-4:]}' if len(str(value)) > 8 else '***'
                self.stdout.write(f'{key}: {value}')