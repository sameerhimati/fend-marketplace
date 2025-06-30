#!/usr/bin/env python
"""
List all files in the S3/DigitalOcean Spaces bucket
Usage: docker-compose exec web python scripts/list_s3_contents.py
"""
import os
import sys
import django

# Add the project directory to Python path
sys.path.insert(0, '/app')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fend.settings.production')
django.setup()

import boto3
from django.conf import settings


def list_s3_contents():
    """List all files in the S3 bucket with details"""
    
    # Check if S3 is enabled
    if not getattr(settings, 'USE_S3', False):
        print("S3/Spaces is not enabled. Set USE_S3=True in settings.")
        return
    
    # Initialize S3 client
    s3_client = boto3.client(
        's3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'sfo3')
    )
    
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    
    print(f"=== LISTING ALL FILES IN BUCKET: {bucket_name} ===")
    print(f"Endpoint: {settings.AWS_S3_ENDPOINT_URL}")
    print("=" * 60)
    
    try:
        # Use paginator to handle large buckets
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name)
        
        total_count = 0
        total_size = 0
        
        # Group files by directory
        files_by_dir = {}
        
        for page in pages:
            if 'Contents' not in page:
                continue
                
            for obj in page['Contents']:
                key = obj['Key']
                size = obj['Size']
                
                # Get directory
                if '/' in key:
                    directory = key.rsplit('/', 1)[0]
                else:
                    directory = '(root)'
                
                if directory not in files_by_dir:
                    files_by_dir[directory] = []
                
                files_by_dir[directory].append({
                    'name': key.rsplit('/', 1)[-1],
                    'full_path': key,
                    'size': size
                })
                
                total_count += 1
                total_size += size
        
        # Print files grouped by directory
        for directory in sorted(files_by_dir.keys()):
            print(f"\n📁 {directory}/")
            for file_info in sorted(files_by_dir[directory], key=lambda x: x['name']):
                size_str = f"{file_info['size']:,}" if file_info['size'] > 0 else "0"
                print(f"  - {file_info['name']} ({size_str} bytes)")
        
        print("\n" + "=" * 60)
        print(f"Total files: {total_count}")
        print(f"Total size: {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)")
        
        # Check specifically for CSS files
        print("\n🔍 CSS Files:")
        css_found = False
        for directory, files in files_by_dir.items():
            for file_info in files:
                if file_info['full_path'].endswith('.css'):
                    print(f"  ✓ {file_info['full_path']}")
                    css_found = True
        
        if not css_found:
            print("  ❌ No CSS files found in bucket!")
            
    except Exception as e:
        print(f"Error listing bucket contents: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    list_s3_contents()