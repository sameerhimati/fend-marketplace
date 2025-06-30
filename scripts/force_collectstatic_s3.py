#!/usr/bin/env python
"""
Force collectstatic to use S3 backend
Usage: docker-compose exec web python scripts/force_collectstatic_s3.py
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
from django.core.management import call_command
from django.contrib.staticfiles.storage import staticfiles_storage


def force_collectstatic_s3():
    """Force collectstatic to use S3"""
    
    print("=== FORCING COLLECTSTATIC WITH S3 ===")
    print(f"USE_S3: {settings.USE_S3}")
    print(f"STATICFILES_STORAGE: {settings.STATICFILES_STORAGE}")
    print(f"Current storage backend: {staticfiles_storage.__class__.__name__}")
    
    # Import the S3 storage backend directly
    from fend.storage_backends import StaticStorage
    
    # Manually copy CSS files to S3
    import os
    from django.core.files.base import File
    
    storage = StaticStorage()
    css_dir = '/app/static/css'
    
    print("\n📤 Manually uploading CSS files to S3...")
    
    if os.path.exists(css_dir):
        for filename in os.listdir(css_dir):
            if filename.endswith('.css'):
                filepath = os.path.join(css_dir, filename)
                with open(filepath, 'rb') as f:
                    s3_path = f'css/{filename}'
                    
                    # Delete if exists
                    if storage.exists(s3_path):
                        storage.delete(s3_path)
                        print(f"  Deleted existing: {s3_path}")
                    
                    # Upload file
                    saved_path = storage.save(s3_path, File(f))
                    print(f"  ✅ Uploaded: {saved_path}")
                    print(f"     URL: {storage.url(saved_path)}")
    
    # Also upload admin CSS
    admin_css_dir = '/usr/local/lib/python3.11/site-packages/django/contrib/admin/static/admin/css'
    print("\n📤 Uploading admin CSS files...")
    
    if os.path.exists(admin_css_dir):
        for filename in os.listdir(admin_css_dir):
            if filename.endswith('.css'):
                filepath = os.path.join(admin_css_dir, filename)
                with open(filepath, 'rb') as f:
                    s3_path = f'admin/css/{filename}'
                    
                    # Upload file
                    saved_path = storage.save(s3_path, File(f))
                    print(f"  ✅ Uploaded: {saved_path}")
    
    print("\n✅ CSS files uploaded to S3!")
    
    # Verify uploads
    print("\n🔍 Verifying CSS files in S3...")
    from scripts.list_s3_contents import list_s3_contents
    list_s3_contents()


if __name__ == '__main__':
    force_collectstatic_s3()