from django.db import migrations

def initialize_tokens_for_enterprises(apps, schema_editor):
    Organization = apps.get_model('organizations', 'Organization')
    
    # Get all enterprise organizations
    enterprises = Organization.objects.filter(type='enterprise')
    
    for enterprise in enterprises:
        if enterprise.token_balance == 0:
            # Default to 1 token for each enterprise
            enterprise.token_balance = 1
            enterprise.tokens_purchased = 1
            enterprise.save()

def reverse_func(apps, schema_editor):
    pass  # No reversal needed

class Migration(migrations.Migration):
    dependencies = [
        ('organizations', '0004_add_token_fields'),
        ('payments', '0001_initial'),  # Add explicit dependency on payments app
    ]

    operations = [
        migrations.RunPython(initialize_tokens_for_enterprises, reverse_func),
    ]
