from django.db import migrations

def initialize_tokens_for_enterprises(apps, schema_editor):
    Organization = apps.get_model('organizations', 'Organization')
    Subscription = apps.get_model('payments', 'Subscription')
    
    # Get all enterprise organizations with active subscriptions
    enterprises = Organization.objects.filter(type='enterprise')
    
    for enterprise in enterprises:
        try:
            subscription = Subscription.objects.get(organization=enterprise)
            if subscription.status == 'active':
                # Add tokens based on subscription plan
                if enterprise.token_balance == 0:
                    # Default to 1 token if plan doesn't specify
                    tokens_to_add = 1
                    
                    # If plan has initial_tokens field, use that value
                    if hasattr(subscription.plan, 'initial_tokens'):
                        tokens_to_add = subscription.plan.initial_tokens or 1
                    
                    enterprise.token_balance = tokens_to_add
                    enterprise.tokens_purchased = tokens_to_add
                    enterprise.save()
        except Subscription.DoesNotExist:
            pass

def reverse_func(apps, schema_editor):
    pass  # No reversal needed

class Migration(migrations.Migration):
    dependencies = [
        ('organizations', '0004_add_token_fields'),
    ]

    operations = [
        migrations.RunPython(initialize_tokens_for_enterprises, reverse_func),
    ]