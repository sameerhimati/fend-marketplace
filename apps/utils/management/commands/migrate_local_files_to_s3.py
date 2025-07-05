import os
import boto3
from django.core.management.base import BaseCommand
from django.conf import settings
from botocore.exceptions import ClientError
import mimetypes


class Command(BaseCommand):
    help = 'Migrate local media files to Digital Ocean Spaces (S3)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be uploaded without actually uploading',
        )
        parser.add_argument(
            '--delete-after',
            action='store_true',
            help='Delete local files after successful upload',
        )

    def handle(self, *args, **options):
        if not getattr(settings, 'USE_S3', False):
            self.stdout.write(
                self.style.ERROR('S3/Spaces is not enabled. Set USE_S3=True in settings.')
            )
            return

        # Initialize S3 client
        try:
            s3_client = boto3.client(
                's3',
                endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'sfo3')
            )

            bucket_name = settings.AWS_STORAGE_BUCKET_NAME

            # Test connection
            s3_client.head_bucket(Bucket=bucket_name)
            self.stdout.write(
                self.style.SUCCESS(f'Connected to bucket: {bucket_name}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to connect to bucket {bucket_name}: {e}')
            )
            return

        media_root = getattr(settings, 'MEDIA_ROOT', '/app/media')
        
        if not os.path.exists(media_root):
            self.stdout.write(
                self.style.ERROR(f'Media root does not exist: {media_root}')
            )
            return

        uploaded = 0
        skipped = 0
        errors = 0
        files_to_delete = []

        # Walk through media directory
        for root, dirs, files in os.walk(media_root):
            for filename in files:
                if filename.startswith('.'):
                    continue
                
                local_path = os.path.join(root, filename)
                
                # Create S3 key by removing media_root prefix
                relative_path = os.path.relpath(local_path, media_root)
                s3_key = f"media/{relative_path}".replace('\\', '/')  # Ensure forward slashes
                
                try:
                    # Check if file already exists in S3
                    try:
                        s3_client.head_object(Bucket=bucket_name, Key=s3_key)
                        self.stdout.write(f"  Already exists: {s3_key}")
                        skipped += 1
                        continue
                    except ClientError as e:
                        if e.response['Error']['Code'] != '404':
                            raise
                    
                    if options['dry_run']:
                        self.stdout.write(f"  Would upload: {local_path} -> {s3_key}")
                        uploaded += 1
                    else:
                        # Determine content type
                        content_type, _ = mimetypes.guess_type(filename)
                        if not content_type:
                            if filename.endswith('.pdf'):
                                content_type = 'application/pdf'
                            elif filename.endswith(('.jpg', '.jpeg')):
                                content_type = 'image/jpeg'
                            elif filename.endswith('.png'):
                                content_type = 'image/png'
                            else:
                                content_type = 'application/octet-stream'
                        
                        # Upload file
                        with open(local_path, 'rb') as f:
                            s3_client.put_object(
                                Bucket=bucket_name,
                                Key=s3_key,
                                Body=f,
                                ACL='public-read',
                                ContentType=content_type
                            )
                        
                        self.stdout.write(
                            self.style.SUCCESS(f"  Uploaded: {local_path} -> {s3_key}")
                        )
                        uploaded += 1
                        files_to_delete.append(local_path)
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  Error uploading {local_path}: {e}")
                    )
                    errors += 1

        # Summary
        self.stdout.write("\n" + "="*50)
        self.stdout.write(
            self.style.SUCCESS(f"Uploaded: {uploaded} files")
        )
        self.stdout.write(f"Skipped (already exists): {skipped} files")
        self.stdout.write(
            self.style.WARNING(f"Errors: {errors} files")
        )

        # Delete local files if requested and not dry run
        if options['delete_after'] and not options['dry_run'] and files_to_delete:
            self.stdout.write("\nDeleting local files...")
            deleted = 0
            for filepath in files_to_delete:
                try:
                    os.remove(filepath)
                    deleted += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  Error deleting {filepath}: {e}")
                    )
            self.stdout.write(
                self.style.SUCCESS(f"Deleted {deleted} local files")
            )