from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.payments.models import FreeAccountCode, PricingPlan


class Command(BaseCommand):
    help = 'Generate free account access codes'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--plan-id',
            type=int,
            required=True,
            help='ID of the pricing plan to grant access to'
        )
        parser.add_argument(
            '--count',
            type=int,
            default=1,
            help='Number of codes to generate (default: 1)'
        )
        parser.add_argument(
            '--description',
            type=str,
            default='',
            help='Description for the codes'
        )
        parser.add_argument(
            '--valid-days',
            type=int,
            default=365,
            help='Number of days the codes are valid for redemption (default: 365)'
        )
        parser.add_argument(
            '--free-months',
            type=int,
            default=12,
            help='Number of months of free access (default: 12)'
        )
        parser.add_argument(
            '--max-uses',
            type=int,
            default=1,
            help='Maximum uses per code (default: 1)'
        )
        parser.add_argument(
            '--prefix',
            type=str,
            default='',
            help='Optional prefix for description (e.g., "Launch Partner")'
        )
    
    def handle(self, *args, **options):
        plan_id = options['plan_id']
        count = options['count']
        description = options['description']
        valid_days = options['valid_days']
        free_months = options['free_months']
        max_uses = options['max_uses']
        prefix = options['prefix']
        
        # Get the plan
        try:
            plan = PricingPlan.objects.get(id=plan_id)
        except PricingPlan.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Plan with ID {plan_id} does not exist.")
            )
            self.stdout.write("Available plans:")
            for p in PricingPlan.objects.filter(is_active=True):
                self.stdout.write(f"  ID {p.id}: {p.name} - ${p.price}/{p.billing_frequency}")
            return
        
        if prefix and not description:
            description = f"{prefix} - Generated {timezone.now().strftime('%Y-%m-%d')}"
        elif not description:
            description = f"Generated {timezone.now().strftime('%Y-%m-%d')}"
        
        self.stdout.write(f"Generating {count} free account code(s) for plan: {plan.name}")
        
        codes = []
        for i in range(count):
            code = FreeAccountCode.generate_code(
                plan=plan,
                description=f"{description} ({i+1}/{count})" if count > 1 else description,
                valid_days=valid_days,
                max_uses=max_uses,
                free_months=free_months
            )
            codes.append(code)
        
        self.stdout.write(
            self.style.SUCCESS(f"Successfully generated {count} free account code(s):")
        )
        
        for code in codes:
            self.stdout.write(f"  Code: {code.code}")
            self.stdout.write(f"    Plan: {code.plan.name}")
            self.stdout.write(f"    Description: {code.description}")
            self.stdout.write(f"    Free months: {code.free_months}")
            self.stdout.write(f"    Valid until: {code.valid_until.strftime('%Y-%m-%d %H:%M')}")
            self.stdout.write(f"    Max uses: {code.max_uses}")
            self.stdout.write("")
        
        self.stdout.write(
            self.style.WARNING(
                "Remember to securely distribute these codes to the intended recipients."
            )
        )