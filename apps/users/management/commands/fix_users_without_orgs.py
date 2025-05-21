from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.users.models import User
from apps.organizations.models import Organization

class Command(BaseCommand):
    help = 'Fix users without organizations'

    def handle(self, *args, **options):
        users_without_orgs = User.objects.filter(organization__isnull=True)
        self.stdout.write(f"Found {users_without_orgs.count()} users without organizations")
        
        for user in users_without_orgs:
            org_name = f"{user.username}'s Organization"
            if user.first_name and user.last_name:
                org_name = f"{user.first_name} {user.last_name}'s Organization"
            
            org_type = 'enterprise' if user.is_staff else 'startup'
            
            # Create organization
            org = Organization.objects.create(
                name=org_name,
                type=org_type,
                website=f"example.com/{user.username}",
                primary_contact_name=user.get_full_name() or user.username,
                primary_contact_phone="0000000000",
                country_code="+1",
                approval_status='approved',
                onboarding_completed=True,
                created_at=timezone.now(),
                updated_at=timezone.now()
            )
            
            # Link user to organization
            user.organization = org
            user.save()
            
            self.stdout.write(self.style.SUCCESS(f"Created organization for {user.username}"))
        
        if users_without_orgs.count() == 0:
            self.stdout.write(self.style.SUCCESS("No users without organizations found"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Fixed {users_without_orgs.count()} users"))