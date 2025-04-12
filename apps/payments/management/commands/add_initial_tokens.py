from django.core.management.base import BaseCommand
from apps.organizations.models import Organization

class Command(BaseCommand):
    help = 'Adds initial tokens to existing enterprise organizations'

    def add_arguments(self, parser):
        parser.add_argument('--tokens', type=int, default=1, help='Number of tokens to add')

    def handle(self, *args, **kwargs):
        token_count = kwargs['tokens']
        enterprises = Organization.objects.filter(type='enterprise')
        
        for enterprise in enterprises:
            if enterprise.token_balance == 0:
                enterprise.token_balance = token_count
                enterprise.tokens_purchased = token_count
                enterprise.save(update_fields=['token_balance', 'tokens_purchased'])
                self.stdout.write(self.style.SUCCESS(f'Added {token_count} tokens to {enterprise.name}'))
            else:
                self.stdout.write(f'Skipped {enterprise.name} (already has {enterprise.token_balance} tokens)')
        
        self.stdout.write(self.style.SUCCESS(f'Process completed for {enterprises.count()} enterprises'))