#!/bin/bash
# Simple script to investigate user access issues

echo "=== USER ACCESS INVESTIGATION ==="
echo "Running investigation..."
echo ""

docker compose exec web python manage.py shell << 'EOF'
from django.utils import timezone
from apps.organizations.models import User
from apps.payments.models import Subscription

print("=== USER ACCESS INVESTIGATION ===")
print(f"Investigation time: {timezone.now()}")
print("")

users = User.objects.select_related('organization').all()
print(f"Total users found: {users.count()}")
print("")

print("User ID | Username     | Org Name     | Approval     | Has Sub | Sub Active | Should Access")
print("-" * 85)

problematic_users = []

for user in users:
    if not user.organization:
        continue
        
    org = user.organization
    org_name = org.name[:12] if org.name else "No Name"
    approval = getattr(org, 'approval_status', 'unknown')[:12]
    
    # Check subscription
    has_subscription = False
    subscription_active = False
    try:
        sub = org.subscription
        has_subscription = True
        subscription_active = sub.is_active()
    except:
        pass
    
    # Check access method
    has_active_method = org.has_active_subscription()
    
    # Should they have access?
    should_have_access = approval == 'approved' and has_active_method
    
    # Format output
    user_id = str(user.id)[:7]
    username = user.username[:12]
    has_sub_str = "Yes" if has_subscription else "No"
    sub_active_str = "Yes" if subscription_active else "No"
    should_access_str = "Yes" if should_have_access else "No"
    
    row = f"{user_id:7} | {username:12} | {org_name:12} | {approval:12} | {has_sub_str:7} | {sub_active_str:10} | {should_access_str:13}"
    
    # Mark problematic users
    if not should_have_access and has_active_method:
        print(f"🚨 {row}")
        problematic_users.append({
            'user': user.username,
            'org': org.name,
            'approval': approval,
            'has_subscription': has_subscription,
            'subscription_active': subscription_active,
            'has_active_method': has_active_method
        })
    elif approval == 'pending':
        print(f"⚠️  {row}")
    else:
        print(row)

print("")
print("=" * 85)
print("SUMMARY:")

total_users = users.count()
approved = users.filter(organization__approval_status='approved').count()
pending = users.filter(organization__approval_status='pending').count()

print(f"Total users: {total_users}")
print(f"Approved organizations: {approved}")
print(f"Pending organizations: {pending}")

if problematic_users:
    print("")
    print("🚨 PROBLEMATIC USERS (shouldn't have access but do):")
    for user in problematic_users:
        print(f"  - {user['user']} ({user['org']})")
        print(f"    Approval: {user['approval']}, Has Sub: {user['has_subscription']}, Sub Active: {user['subscription_active']}, Method Returns: {user['has_active_method']}")
else:
    print("")
    print("✅ No problematic users found!")

print("")
print("Investigation complete.")
EOF