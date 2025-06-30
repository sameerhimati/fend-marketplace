import os
import boto3
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Fix ACL permissions for static and media files in S3/Spaces'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually making changes',
        )
        parser.add_argument(
            '--static-only',
            action='store_true',
            help='Only fix static files permissions',
        )
        parser.add_argument(
            '--media-only',
            action='store_true',
            help='Only fix media files permissions',
        )

    def handle(self, *args, **options):
        if not getattr(settings, 'USE_S3', False):
            self.stdout.write(
                self.style.ERROR('S3/Spaces is not enabled. Set USE_S3=True in settings.')
            )
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

        try:
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

        # Determine which folders to fix
        folders_to_fix = []
        if not options['media_only']:
            folders_to_fix.append('static/')
        if not options['static_only']:
            folders_to_fix.append('media/')

        for folder in folders_to_fix:
            self.stdout.write(f'\nProcessing {folder} folder...')
            self.fix_folder_permissions(s3_client, bucket_name, folder, options['dry_run'])

        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING('\nDry run completed. No changes were made.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('\nPermissions update completed!')
            )

    def fix_folder_permissions(self, s3_client, bucket_name, folder, dry_run=False):
        """Fix permissions for all objects in a folder"""
        
        try:
            # List all objects in the folder
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket_name, Prefix=folder)

            object_count = 0
            updated_count = 0

            for page in pages:
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    object_count += 1
                    key = obj['Key']
                    
                    # Skip folders (keys ending with '/')
                    if key.endswith('/'):
                        continue

                    try:
                        # Check current ACL
                        current_acl = s3_client.get_object_acl(Bucket=bucket_name, Key=key)
                        
                        # Check if public-read is already set
                        has_public_read = False
                        for grant in current_acl.get('Grants', []):
                            grantee = grant.get('Grantee', {})
                            if (grantee.get('Type') == 'Group' and 
                                grantee.get('URI') == 'http://acs.amazonaws.com/groups/global/AllUsers' and
                                grant.get('Permission') == 'READ'):
                                has_public_read = True
                                break

                        if not has_public_read:
                            if dry_run:
                                self.stdout.write(f'  Would update: {key}')
                            else:
                                # Set public-read ACL
                                s3_client.put_object_acl(
                                    Bucket=bucket_name,
                                    Key=key,
                                    ACL='public-read'
                                )
                                self.stdout.write(f'  Updated: {key}')
                            updated_count += 1
                        else:
                            self.stdout.write(f'  Already public: {key}')

                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'  Failed to process {key}: {e}')
                        )

            self.stdout.write(
                self.style.SUCCESS(
                    f'Processed {object_count} objects in {folder} '
                    f'({updated_count} needed updates)'
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to process folder {folder}: {e}')
            )