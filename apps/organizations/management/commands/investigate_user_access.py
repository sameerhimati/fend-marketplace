from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.organizations.models import Organization, User
from apps.payments.models import Subscription, FreeAccountCode
import json


class Command(BaseCommand):
    help = 'Investigate user access and subscription states to debug access control issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            choices=['json', 'table'],
            default='table',
            help='Output format (default: table)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Include additional details'
        )

    def handle(self, *args, **options):
        self.style = self.style  # Enable colored output
        users_data = []

        # Get all users with organizations
        users = User.objects.select_related('organization').all()
        
        self.stdout.write(self.style.SUCCESS(f"=== USER ACCESS INVESTIGATION ==="))
        self.stdout.write(f"Total users found: {users.count()}")
        self.stdout.write(f"Investigation time: {timezone.now()}")
        self.stdout.write("")

        for user in users:
            if not user.organization:
                continue
                
            org = user.organization
            user_data = {
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'org_id': org.id,
                'org_name': org.name,
                'org_type': org.type,
                'approval_status': getattr(org, 'approval_status', 'No approval status'),
                'approval_date': getattr(org, 'approval_date', None),
            }

            # Check subscription
            subscription = None
            try:
                subscription = org.subscription
                user_data.update({
                    'has_subscription': True,
                    'subscription_id': subscription.id,
                    'subscription_status': subscription.status,
                    'subscription_start': subscription.current_period_start,
                    'subscription_end': subscription.current_period_end,
                    'stripe_customer_id': subscription.stripe_customer_id,
                    'stripe_subscription_id': subscription.stripe_subscription_id,
                })
                
                # Check if subscription is truly active
                user_data['subscription_is_active'] = subscription.is_active()
                
                # Check for promo code
                if subscription.free_account_code:
                    code = subscription.free_account_code
                    user_data.update({
                        'has_promo_code': True,
                        'promo_code': code.code,
                        'promo_code_valid': code.is_valid(),
                        'promo_code_expires': code.valid_until,
                        'promo_code_plan': code.plan.name if code.plan else None,
                    })
                else:
                    user_data['has_promo_code'] = False
                    
            except Subscription.DoesNotExist:
                user_data.update({
                    'has_subscription': False,
                    'subscription_is_active': False,
                    'has_promo_code': False,
                })

            # Test access control methods
            user_data['has_active_subscription_method'] = org.has_active_subscription()
            
            # Determine what access they should have
            should_have_access = (
                getattr(org, 'approval_status', 'pending') == 'approved' and
                user_data['has_active_subscription_method']
            )
            user_data['should_have_access'] = should_have_access
            
            # Determine access level
            if getattr(org, 'approval_status', 'pending') == 'pending':
                user_data['expected_ui_state'] = 'pending_approval'
            elif getattr(org, 'approval_status', 'pending') == 'rejected':
                user_data['expected_ui_state'] = 'minimal'
            elif not user_data['has_active_subscription_method']:
                user_data['expected_ui_state'] = 'subscription'
            else:
                user_data['expected_ui_state'] = 'full'
            
            users_data.append(user_data)

        # Output results
        if options['format'] == 'json':
            self.output_json(users_data)
        else:
            self.output_table(users_data, options['verbose'])

        # Summary
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.SUCCESS("SUMMARY:"))
        
        total_users = len(users_data)
        with_orgs = len([u for u in users_data if u['org_id']])
        approved = len([u for u in users_data if u['approval_status'] == 'approved'])
        pending = len([u for u in users_data if u['approval_status'] == 'pending'])
        rejected = len([u for u in users_data if u['approval_status'] == 'rejected'])
        with_subscription = len([u for u in users_data if u['has_subscription']])
        with_active_subscription = len([u for u in users_data if u['subscription_is_active']])
        with_promo = len([u for u in users_data if u['has_promo_code']])
        should_have_access = len([u for u in users_data if u['should_have_access']])
        
        self.stdout.write(f"Total users: {total_users}")
        self.stdout.write(f"Users with organizations: {with_orgs}")
        self.stdout.write(f"Approved organizations: {approved}")
        self.stdout.write(f"Pending organizations: {pending}")
        self.stdout.write(f"Rejected organizations: {rejected}")
        self.stdout.write(f"Users with subscriptions: {with_subscription}")
        self.stdout.write(f"Users with active subscriptions: {with_active_subscription}")
        self.stdout.write(f"Users with promo codes: {with_promo}")
        self.stdout.write(f"Users who should have full access: {should_have_access}")
        
        # Identify problematic cases
        self.stdout.write("\n" + self.style.WARNING("POTENTIAL ISSUES:"))
        
        problematic = []
        for user_data in users_data:
            issues = []
            
            # Check for expired promo codes with access
            if (user_data['has_promo_code'] and 
                not user_data.get('promo_code_valid', False) and 
                user_data['has_active_subscription_method']):
                issues.append("Has expired promo code but has_active_subscription() returns True")
            
            # Check for users without subscriptions but with access  
            if (not user_data['has_subscription'] and 
                user_data['has_active_subscription_method']):
                issues.append("No subscription but has_active_subscription() returns True")
                
            # Check for inactive subscriptions with access
            if (user_data['has_subscription'] and 
                not user_data['subscription_is_active'] and 
                user_data['has_active_subscription_method']):
                issues.append("Inactive subscription but has_active_subscription() returns True")
            
            if issues:
                problematic.append({
                    'user': f"{user_data['username']} (ID: {user_data['user_id']})",
                    'org': f"{user_data['org_name']} (ID: {user_data['org_id']})",
                    'issues': issues
                })
        
        if problematic:
            for problem in problematic:
                self.stdout.write(f"\n🚨 {problem['user']} - {problem['org']}")
                for issue in problem['issues']:
                    self.stdout.write(f"   - {issue}")
        else:
            self.stdout.write(self.style.SUCCESS("No access control issues detected!"))

    def output_json(self, users_data):
        # Convert datetime objects to strings for JSON serialization
        for user_data in users_data:
            for key, value in user_data.items():
                if hasattr(value, 'isoformat'):
                    user_data[key] = value.isoformat()
        
        self.stdout.write(json.dumps(users_data, indent=2, default=str))

    def output_table(self, users_data, verbose=False):
        if not users_data:
            self.stdout.write("No users found.")
            return
            
        # Table headers
        headers = [
            "User ID", "Username", "Org Name", "Approval", "Has Sub", "Sub Active", 
            "Promo Code", "Should Access", "Expected UI"
        ]
        
        if verbose:
            headers.extend(["Sub Status", "Sub Expires", "Promo Valid"])
        
        # Print headers
        header_line = " | ".join(f"{h:12}" for h in headers)
        self.stdout.write(header_line)
        self.stdout.write("-" * len(header_line))
        
        # Print data rows
        for user_data in users_data:
            row_data = [
                str(user_data['user_id'])[:12],
                user_data['username'][:12],
                user_data['org_name'][:12],
                user_data['approval_status'][:12],
                "Yes" if user_data['has_subscription'] else "No",
                "Yes" if user_data['subscription_is_active'] else "No",
                "Yes" if user_data['has_promo_code'] else "No",
                "Yes" if user_data['should_have_access'] else "No",
                user_data['expected_ui_state'][:12],
            ]
            
            if verbose:
                row_data.extend([
                    user_data.get('subscription_status', 'None')[:12],
                    str(user_data.get('subscription_end', 'None'))[:12],
                    "Yes" if user_data.get('promo_code_valid', False) else "No",
                ])
            
            row_line = " | ".join(f"{str(d):12}" for d in row_data)
            
            # Color code problematic rows
            if not user_data['should_have_access'] and user_data['has_active_subscription_method']:
                self.stdout.write(self.style.ERROR(row_line))
            elif user_data['approval_status'] == 'pending':
                self.stdout.write(self.style.WARNING(row_line))
            else:
                self.stdout.write(row_line)