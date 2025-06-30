#!/usr/bin/env python
"""
Test CSS file upload to S3/DigitalOcean Spaces
Usage: docker-compose exec web python scripts/test_css_upload.py
"""
import os
import sys
import django

# Add the project directory to Python path
sys.path.insert(0, '/app')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fend.settings.production')
django.setup()

from django.conf import settings
from django.core.files.base import ContentFile
from storages.backends.s3boto3 import S3Boto3Storage


def test_css_upload():
    """Test uploading CSS files to S3"""
    
    print("=== TESTING CSS UPLOAD TO S3 ===")
    print(f"USE_S3: {settings.USE_S3}")
    print(f"STATICFILES_STORAGE: {settings.STATICFILES_STORAGE}")
    print(f"Bucket: {settings.AWS_STORAGE_BUCKET_NAME}")
    print(f"Endpoint: {settings.AWS_S3_ENDPOINT_URL}")
    print("=" * 50)
    
    # Check if static storage is using S3
    from django.contrib.staticfiles.storage import staticfiles_storage
    print(f"\nStatic storage class: {staticfiles_storage.__class__.__name__}")
    print(f"Static storage location: {getattr(staticfiles_storage, 'location', 'Not set')}")
    
    # Initialize storage directly
    static_storage = S3Boto3Storage(
        bucket_name=settings.AWS_STORAGE_BUCKET_NAME,
        location='static',
        default_acl='public-read',
        file_overwrite=True
    )
    
    # Test uploading a CSS file
    test_css = b"""/* Test CSS file */
.test-class {
    color: red;
    background: blue;
}"""
    
    try:
        # Save test CSS file
        path = static_storage.save('css/test-upload.css', ContentFile(test_css))
        print(f"\n✅ Successfully uploaded: {path}")
        print(f"Full URL: {static_storage.url(path)}")
        
        # Check if it exists
        exists = static_storage.exists(path)
        print(f"File exists: {exists}")
        
        # Try to list CSS directory
        print("\n📁 Listing static/css/ directory in S3:")
        files = list(static_storage.listdir('css')[1])
        for f in files:
            print(f"  - {f}")
            
    except Exception as e:
        print(f"\n❌ Error uploading CSS: {e}")
        import traceback
        traceback.print_exc()
    
    # Check local CSS files
    print("\n📁 Local CSS files in /app/static/css/:")
    css_dir = '/app/static/css'
    if os.path.exists(css_dir):
        for f in os.listdir(css_dir):
            filepath = os.path.join(css_dir, f)
            size = os.path.getsize(filepath)
            print(f"  - {f} ({size} bytes)")
    else:
        print("  ❌ Directory doesn't exist!")
        
    print("\n📁 Local CSS files in /app/staticfiles/css/:")
    css_dir = '/app/staticfiles/css'
    if os.path.exists(css_dir):
        for f in os.listdir(css_dir):
            filepath = os.path.join(css_dir, f)
            size = os.path.getsize(filepath)
            print(f"  - {f} ({size} bytes)")
    else:
        print("  ❌ Directory doesn't exist!")


if __name__ == '__main__':
    test_css_upload()