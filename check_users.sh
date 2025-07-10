#!/bin/bash
# Simple script to investigate user access issues

echo "=== USER ACCESS INVESTIGATION ==="
docker compose exec -T web python manage.py shell -c "
from apps.users.models import User
users = User.objects.select_related('organization').all()
print(f'Total users: {users.count()}')
print('')
for user in users:
    if user.organization:
        org = user.organization
        approval = getattr(org, 'approval_status', 'unknown')
        has_active = org.has_active_subscription()
        try:
            sub = org.subscription
            sub_active = sub.is_active()
            print(f'User: {user.username} | Org: {org.name} | Approval: {approval} | has_active_subscription(): {has_active} | subscription.is_active(): {sub_active}')
        except:
            print(f'User: {user.username} | Org: {org.name} | Approval: {approval} | has_active_subscription(): {has_active} | No subscription')
"