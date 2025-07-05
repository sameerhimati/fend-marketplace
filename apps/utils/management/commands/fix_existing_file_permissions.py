import os
import boto3
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.pilots.models import Pilot, PilotBid
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = 'Fix ACL permissions for existing uploaded files (pilots, bids, logos)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually making changes',
        )
        parser.add_argument(
            '--pilots-only',
            action='store_true',
            help='Only fix pilot file permissions',
        )
        parser.add_argument(
            '--bids-only',
            action='store_true',
            help='Only fix bid file permissions',
        )
        parser.add_argument(
            '--logos-only',
            action='store_true',
            help='Only fix logo permissions',
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

        # Determine what to fix
        fix_pilots = not (options['bids_only'] or options['logos_only'])
        fix_bids = not (options['pilots_only'] or options['logos_only'])
        fix_logos = not (options['pilots_only'] or options['bids_only'])

        total_fixed = 0

        if fix_pilots:
            self.stdout.write('\n=== Fixing Pilot File Permissions ===')
            total_fixed += self.fix_pilot_files(s3_client, bucket_name, options['dry_run'])

        if fix_bids:
            self.stdout.write('\n=== Fixing Bid File Permissions ===')
            total_fixed += self.fix_bid_files(s3_client, bucket_name, options['dry_run'])

        if fix_logos:
            self.stdout.write('\n=== Fixing Logo Permissions ===')
            total_fixed += self.fix_logo_files(s3_client, bucket_name, options['dry_run'])

        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(f'\nDry run completed. {total_fixed} files would be updated.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\nCompleted! {total_fixed} files updated.')
            )

    def fix_pilot_files(self, s3_client, bucket_name, dry_run=False):
        """Fix permissions for pilot document files"""
        fixed_count = 0
        
        pilots = Pilot.objects.all()
        self.stdout.write(f'Processing {pilots.count()} pilots...')
        
        for pilot in pilots:
            # Technical specs documents
            if pilot.technical_specs_doc:
                if self.fix_file_permission(s3_client, bucket_name, pilot.technical_specs_doc.name, dry_run):
                    fixed_count += 1
                    
            # Performance metrics documents
            if pilot.performance_metrics_doc:
                if self.fix_file_permission(s3_client, bucket_name, pilot.performance_metrics_doc.name, dry_run):
                    fixed_count += 1
                    
            # Compliance requirements documents
            if pilot.compliance_requirements_doc:
                if self.fix_file_permission(s3_client, bucket_name, pilot.compliance_requirements_doc.name, dry_run):
                    fixed_count += 1

        self.stdout.write(f'Pilot files: {fixed_count} files fixed/would be fixed')
        return fixed_count

    def fix_bid_files(self, s3_client, bucket_name, dry_run=False):
        """Fix permissions for bid proposal files"""
        fixed_count = 0
        
        bids = PilotBid.objects.filter(proposal_doc__isnull=False)
        self.stdout.write(f'Processing {bids.count()} bids with documents...')
        
        for bid in bids:
            if bid.proposal_doc:
                if self.fix_file_permission(s3_client, bucket_name, bid.proposal_doc.name, dry_run):
                    fixed_count += 1

        self.stdout.write(f'Bid files: {fixed_count} files fixed/would be fixed')
        return fixed_count

    def fix_logo_files(self, s3_client, bucket_name, dry_run=False):
        """Fix permissions for organization logos"""
        fixed_count = 0
        
        orgs = Organization.objects.filter(logo__isnull=False)
        self.stdout.write(f'Processing {orgs.count()} organizations with logos...')
        
        for org in orgs:
            if org.logo:
                if self.fix_file_permission(s3_client, bucket_name, org.logo.name, dry_run):
                    fixed_count += 1

        self.stdout.write(f'Logo files: {fixed_count} files fixed/would be fixed')
        return fixed_count

    def fix_file_permission(self, s3_client, bucket_name, file_key, dry_run=False):
        """Fix permission for a single file"""
        try:
            # Check if file exists
            try:
                s3_client.head_object(Bucket=bucket_name, Key=file_key)
            except s3_client.exceptions.NoSuchKey:
                self.stdout.write(
                    self.style.WARNING(f'  File not found in S3: {file_key}')
                )
                return False

            # Check current ACL
            current_acl = s3_client.get_object_acl(Bucket=bucket_name, Key=file_key)
            
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
                    self.stdout.write(f'  Would update: {file_key}')
                else:
                    # Set public-read ACL
                    s3_client.put_object_acl(
                        Bucket=bucket_name,
                        Key=file_key,
                        ACL='public-read'
                    )
                    self.stdout.write(f'  Updated: {file_key}')
                return True
            else:
                self.stdout.write(f'  Already public: {file_key}')
                return False

        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'  Failed to process {file_key}: {e}')
            )
            return False