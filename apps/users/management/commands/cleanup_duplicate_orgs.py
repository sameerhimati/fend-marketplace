from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.users.models import User
from apps.organizations.models import Organization
from django.db import transaction

class Command(BaseCommand):
    help = 'Clean up duplicate organizations created by signal handler bug'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find organizations that look like they were auto-generated
        auto_generated_orgs = Organization.objects.filter(
            website__startswith='example.com/',
            approval_status='approved',
            onboarding_completed=True
        )
        
        duplicates_found = 0
        duplicates_deleted = 0
        
        for org in auto_generated_orgs:
            # Check if this organization has any users
            user_count = org.users.count()
            
            if user_count == 0:
                # No users - safe to delete
                if dry_run:
                    self.stdout.write(f"WOULD DELETE: {org.name} (no users)")
                else:
                    org.delete()
                    duplicates_deleted += 1
                duplicates_found += 1
                
            elif user_count == 1:
                # One user - check if they have another organization they should belong to
                user = org.users.first()
                
                # Look for a properly created organization with the same email domain
                email_domain = user.email.split('@')[-1] if user.email else None
                if email_domain:
                    proper_orgs = Organization.objects.filter(
                        users__email__endswith=f'@{email_domain}'
                    ).exclude(
                        id=org.id,
                        website__startswith='example.com/'
                    )
                    
                    if proper_orgs.exists():
                        proper_org = proper_orgs.first()
                        if dry_run:
                            self.stdout.write(
                                f"WOULD MOVE: {user.email} from {org.name} to {proper_org.name}"
                            )
                            self.stdout.write(f"WOULD DELETE: {org.name}")
                        else:
                            # Move user to proper organization
                            user.organization = proper_org
                            user.save()
                            # Delete the auto-generated org
                            org.delete()
                            duplicates_deleted += 1
                        duplicates_found += 1
                    else:
                        self.stdout.write(
                            f"KEEPING: {org.name} (user {user.email} has no proper org to move to)"
                        )
            else:
                self.stdout.write(
                    f"KEEPING: {org.name} ({user_count} users - manual review needed)"
                )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Found {duplicates_found} duplicate organizations. "
                    f"Run without --dry-run to actually clean them up."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Cleaned up {duplicates_deleted} duplicate organizations out of {duplicates_found} found."
                )
            )