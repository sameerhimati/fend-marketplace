from django.core.management.base import BaseCommand
from django.conf import settings
from apps.pilots.models import Pilot, PilotBid
from apps.organizations.models import Organization
import boto3
from botocore.exceptions import ClientError


class Command(BaseCommand):
    help = 'Fix file permissions in Digital Ocean Spaces to make them publicly accessible'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what permissions would be fixed without actually changing them',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if not getattr(settings, 'USE_S3', False):
            self.stdout.write(self.style.WARNING("S3/Spaces storage is not enabled. Skipping permission fixes."))
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No permissions will be changed"))
        
        # Initialize S3 client for Digital Ocean Spaces
        try:
            session = boto3.session.Session()
            client = session.client(
                's3',
                region_name=settings.AWS_S3_REGION_NAME,
                endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
            
            bucket_name = settings.AWS_STORAGE_BUCKET_NAME
            self.stdout.write(f"Connected to bucket: {bucket_name}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to connect to Digital Ocean Spaces: {e}"))
            return
        
        # Collect all file paths from database
        files_to_fix = []
        
        # Pilot files
        for pilot in Pilot.objects.all():
            if pilot.technical_specs_doc:
                files_to_fix.append(('pilot_technical', pilot.technical_specs_doc.name))
            if pilot.performance_metrics_doc:
                files_to_fix.append(('pilot_performance', pilot.performance_metrics_doc.name))
            if pilot.compliance_requirements_doc:
                files_to_fix.append(('pilot_compliance', pilot.compliance_requirements_doc.name))
        
        # Bid files
        for bid in PilotBid.objects.all():
            if bid.proposal_doc:
                files_to_fix.append(('bid_proposal', bid.proposal_doc.name))
        
        # Organization logos
        for org in Organization.objects.all():
            if org.logo:
                files_to_fix.append(('org_logo', org.logo.name))
        
        self.stdout.write(f"Found {len(files_to_fix)} files to check")
        
        fixed_count = 0
        error_count = 0
        
        for file_type, file_path in files_to_fix:
            try:
                # Check current ACL
                try:
                    response = client.get_object_acl(Bucket=bucket_name, Key=file_path)
                    current_acl = response.get('Grants', [])
                    
                    # Check if public-read is already set
                    has_public_read = any(
                        grant.get('Grantee', {}).get('URI') == 'http://acs.amazonaws.com/groups/global/AllUsers'
                        and grant.get('Permission') == 'READ'
                        for grant in current_acl
                    )
                    
                    if has_public_read:
                        self.stdout.write(f"✓ {file_path} - Already public")
                        continue
                        
                except ClientError as e:
                    if e.response['Error']['Code'] == 'NoSuchKey':
                        self.stdout.write(f"⚠ {file_path} - File not found in storage")
                        continue
                    else:
                        raise e
                
                # Fix the ACL
                if dry_run:
                    self.stdout.write(f"Would fix: {file_path}")
                else:
                    client.put_object_acl(
                        Bucket=bucket_name,
                        Key=file_path,
                        ACL='public-read'
                    )
                    self.stdout.write(f"✓ Fixed: {file_path}")
                    fixed_count += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Error fixing {file_path}: {e}"))
                error_count += 1
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would fix permissions on {len([f for f_type, f_path in files_to_fix])} files. "
                    "Run without --dry-run to actually fix them."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Fixed permissions on {fixed_count} files. "
                    f"Errors: {error_count}"
                )
            )
            
            if fixed_count > 0:
                self.stdout.write("Files should now be publicly accessible!")