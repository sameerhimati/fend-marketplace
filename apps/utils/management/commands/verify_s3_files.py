import boto3
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.pilots.models import Pilot, PilotBid
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = 'Verify which files exist in S3 and which are missing'

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
            
            # Get all objects in bucket
            all_objects = set()
            paginator = s3_client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=bucket_name):
                for obj in page.get('Contents', []):
                    all_objects.add(obj['Key'])
            
            self.stdout.write(
                self.style.SUCCESS(f'Found {len(all_objects)} total objects in bucket')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to connect to bucket: {e}')
            )
            return

        # Check pilot files
        self.stdout.write("\n=== Checking Pilot Files ===")
        pilot_exists = 0
        pilot_missing = 0
        
        for pilot in Pilot.objects.all():
            files_to_check = []
            
            if pilot.technical_specs_doc:
                files_to_check.append(('Technical Specs', pilot.technical_specs_doc.name))
            if pilot.performance_metrics_doc:
                files_to_check.append(('Performance Metrics', pilot.performance_metrics_doc.name))
            if pilot.compliance_requirements_doc:
                files_to_check.append(('Compliance', pilot.compliance_requirements_doc.name))
            
            for doc_type, file_path in files_to_check:
                # Check both with and without 'media/' prefix
                if file_path in all_objects or f"media/{file_path}" in all_objects:
                    pilot_exists += 1
                else:
                    pilot_missing += 1
                    self.stdout.write(
                        self.style.WARNING(f"  Missing: Pilot {pilot.id} - {doc_type}: {file_path}")
                    )

        # Check bid files
        self.stdout.write("\n=== Checking Bid Files ===")
        bid_exists = 0
        bid_missing = 0
        
        for bid in PilotBid.objects.filter(proposal_doc__isnull=False):
            file_path = bid.proposal_doc.name
            if file_path in all_objects or f"media/{file_path}" in all_objects:
                bid_exists += 1
            else:
                bid_missing += 1
                self.stdout.write(
                    self.style.WARNING(f"  Missing: Bid {bid.id} - {file_path}")
                )

        # Check organization logos
        self.stdout.write("\n=== Checking Organization Logos ===")
        logo_exists = 0
        logo_missing = 0
        
        for org in Organization.objects.filter(logo__isnull=False):
            file_path = org.logo.name
            if file_path in all_objects or f"media/{file_path}" in all_objects:
                logo_exists += 1
            else:
                logo_missing += 1
                self.stdout.write(
                    self.style.WARNING(f"  Missing: Org {org.name} - {file_path}")
                )

        # Summary
        self.stdout.write("\n" + "="*50)
        self.stdout.write("Summary:")
        self.stdout.write(f"  Pilot files: {pilot_exists} exist, {pilot_missing} missing")
        self.stdout.write(f"  Bid files: {bid_exists} exist, {bid_missing} missing")
        self.stdout.write(f"  Logo files: {logo_exists} exist, {logo_missing} missing")
        self.stdout.write(
            self.style.SUCCESS(f"  Total: {pilot_exists + bid_exists + logo_exists} exist") + ", " +
            self.style.ERROR(f"{pilot_missing + bid_missing + logo_missing} missing")
        )