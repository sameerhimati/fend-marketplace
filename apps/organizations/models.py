from django.db import models
from django.core.validators import URLValidator
from django.db.models.signals import post_save
from apps.payments.models import Subscription
from django.conf import settings
from django.dispatch import receiver
import phonenumbers
from django.core.exceptions import ValidationError
from datetime import datetime

# Onboarding model will be defined below

class Organization(models.Model):
    ORGANIZATION_TYPES = (
        ('enterprise', 'Enterprise'),
        ('startup', 'Startup'),
    )
    
    BUSINESS_TYPES = (
        ('', 'Select One'),
        ('c_corp', 'C-Corporation'),
        ('s_corp', 'S-Corporation'),
        ('llc', 'LLC'),
        ('international', 'International'),
    )
    
    APPROVAL_STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    EMPLOYEE_COUNT_CHOICES = (
        ('', 'Select employee count'),
        ('1-10', '1-10 employees'),
        ('11-50', '11-50 employees'),
        ('51-200', '51-200 employees'),
        ('201-1000', '201-1000 employees'),
        ('1000+', '1000+ employees'),
    )

    # Basic Organization Info
    name = models.CharField(max_length=50)
    type = models.CharField(max_length=20, choices=ORGANIZATION_TYPES)
    website = models.CharField(max_length=100, help_text="Your company website (without http://)")
    industry_tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Industry tags for better matching (e.g., ['AI/ML', 'FinTech', 'SaaS'])"
    )
    business_type = models.CharField(
        max_length=20, 
        choices=BUSINESS_TYPES,
        null=True,
        blank=True
    )
    business_registration_number = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Format: country-code-number"
    )
    tax_identification_number = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    description = models.TextField(blank=True, null=True, help_text="Company description")
    logo = models.ImageField(upload_to='logos/', blank=True, null=True)

    # Extended Company Information (New fields)
    employee_count = models.CharField(
        max_length=20,
        choices=EMPLOYEE_COUNT_CHOICES,
        blank=True,
        null=True,
        help_text="Number of employees in your organization"
    )
    founding_year = models.IntegerField(
        blank=True,
        null=True,
        help_text="Year the company was founded"
    )
    headquarters_location = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="City, State/Country where your headquarters is located"
    )

    linkedin_url = models.URLField(
        blank=True,
        null=True,
        help_text="LinkedIn company page URL"
    )
    twitter_url = models.URLField(
        blank=True,
        null=True,
        help_text="Twitter/X profile URL"
    )

    # Primary Contact Info
    primary_contact_name = models.CharField(max_length=255, null=True, blank=True)
    primary_contact_phone = models.CharField(max_length=20, null=True, blank=True)
    country_code = models.CharField(max_length=5, default='+1', null=True, blank=True)

    # Approval Status
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS_CHOICES,
        default='pending'
    )
    approval_date = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    onboarding_completed = models.BooleanField(default=False)

    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)
    has_payment_method = models.BooleanField(default=False)
    free_trial_used = models.BooleanField(default=False)

    bank_name = models.CharField(max_length=255, blank=True, null=True)
    bank_account_number = models.CharField(max_length=255, blank=True, null=True)
    bank_routing_number = models.CharField(max_length=255, blank=True, null=True)
    
    published_pilot_count = models.IntegerField(default=0, help_text="Number of published pilots")

    # Legal document acceptance tracking
    terms_of_service_accepted = models.BooleanField(default=False)
    terms_of_service_accepted_at = models.DateTimeField(null=True, blank=True)

    privacy_policy_accepted = models.BooleanField(default=False)
    privacy_policy_accepted_at = models.DateTimeField(null=True, blank=True)

    user_agreement_accepted = models.BooleanField(default=False)
    user_agreement_accepted_at = models.DateTimeField(null=True, blank=True)

    payment_terms_accepted = models.BooleanField(default=False)
    payment_terms_accepted_at = models.DateTimeField(null=True, blank=True)

    payment_holding_agreement_accepted = models.BooleanField(default=False)
    payment_holding_agreement_accepted_at = models.DateTimeField(null=True, blank=True)

    data_processing_agreement_accepted = models.BooleanField(default=False)
    data_processing_agreement_accepted_at = models.DateTimeField(null=True, blank=True)

    product_listing_agreement_accepted = models.BooleanField(default=False)
    product_listing_agreement_accepted_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        super().clean()
        
        # Validate founding year
        if self.founding_year:
            current_year = datetime.now().year
            if self.founding_year < 1800 or self.founding_year > current_year:
                raise ValidationError(f"Founding year must be between 1800 and {current_year}")

        # Only validate enterprise-specific fields if type is enterprise 
        # AND onboarding_completed is True (means they've gone through all steps)
        if self.type == 'enterprise' and self.onboarding_completed:
            required_fields = [
                'business_type',
                'business_registration_number',
                'tax_identification_number',
                'primary_contact_name',
                'primary_contact_phone'
            ]
            
            for field in required_fields:
                if not getattr(self, field):
                    raise ValidationError(f"{field.replace('_', ' ').title()} is required for enterprise organizations.")

            # Validate phone number format
            try:
                if self.primary_contact_phone:
                    parsed_number = phonenumbers.parse(self.primary_contact_phone, None)
                    if not phonenumbers.is_valid_number(parsed_number):
                        raise ValidationError("Invalid phone number format")
            except phonenumbers.NumberParseException:
                raise ValidationError("Invalid phone number format")

    def has_active_subscription(self):
        """
        Check if the organization has an active subscription.
        
        Returns:
            bool: True if the organization has an active subscription, False otherwise.
        """
        try:
            # Check if the organization has a subscription relation
            if not hasattr(self, 'subscription'):
                return False
                
            # Check if the subscription exists and is active
            return self.subscription is not None and self.subscription.status == 'active'
        except Exception:
            # Handle any errors gracefully
            return False
        
    def get_remaining_pilots(self):
        """Get number of remaining pilots that can be published"""
        try:
            subscription = self.subscription
            if not subscription.is_active():
                return 0
                
            if subscription.plan.pilot_limit is None:
                return float('inf')  # Unlimited
            
            remaining = max(0, subscription.plan.pilot_limit - self.published_pilot_count)
            return remaining
        except (Subscription.DoesNotExist, AttributeError):
            return 0
    
    def can_publish_more_pilots(self):
        """Check if organization can publish more pilots"""
        remaining = self.get_remaining_pilots()
        return remaining > 0 or remaining == float('inf')
    
    def increment_published_pilots(self):
        """Increment the published pilot count. Returns True if successful."""
        if self.can_publish_more_pilots():
            self.published_pilot_count += 1
            self.save(update_fields=['published_pilot_count'])
            return True
        return False
        
    def can_create_pilot(self):
        """Check if the organization can create new pilots (draft only)"""
        if self.type != 'enterprise':
            return False
        
        # Only need platform access (active subscription) to create draft pilots
        return self.has_active_subscription()
            
    def can_publish_pilot(self):
        """Check if the organization can publish pilots (requires available pilot slots)"""
        if not self.can_create_pilot():
            return False
            
        # Check if organization has available pilot slots
        return self.can_publish_more_pilots()

    def has_required_legal_acceptances(self):
        """Check if organization has accepted all required legal documents for registration"""
        required_docs = [
            self.terms_of_service_accepted,
            self.privacy_policy_accepted, 
            self.user_agreement_accepted
        ]
        
        # EU users also need data processing agreement
        if self.is_eu_based():
            required_docs.append(self.data_processing_agreement_accepted)
        
        return all(required_docs)

    def has_payment_legal_acceptances(self):
        """Check if organization has accepted payment-related legal documents"""
        return (self.payment_terms_accepted and 
                self.payment_holding_agreement_accepted)

    def has_deals_legal_acceptances(self):
        """Check if organization has accepted deals program legal documents"""
        return self.product_listing_agreement_accepted

    def is_eu_based(self):
        """Check if organization is EU-based"""
        eu_countries = ['DE', 'FR', 'ES', 'IT', 'NL', 'BE', 'AT', 'PL', 'SE', 'DK', 'FI', 'IE', 'GB']
        return any(code in (self.headquarters_location or '') for code in eu_countries)

    def accept_legal_document(self, document_type):
        """Accept a legal document and record timestamp"""
        from django.utils import timezone
        
        accepted_field = f"{document_type}_accepted"
        timestamp_field = f"{document_type}_accepted_at"
        
        if hasattr(self, accepted_field) and hasattr(self, timestamp_field):
            setattr(self, accepted_field, True)
            setattr(self, timestamp_field, timezone.now())
            self.save(update_fields=[accepted_field, timestamp_field])
            return True
        return False

    def __str__(self):
        return self.name


class PartnerPromotion(models.Model):
    """
    Model for exclusive deals and partner promotions that organizations can display on their profiles
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='partner_promotions'
    )
    title = models.CharField(
        max_length=100,
        help_text="Title of the exclusive offer or partnership"
    )
    description = models.TextField(
        max_length=500,
        blank=True,
        help_text="Brief description of what this deal offers"
    )
    link_url = models.URLField(
        help_text="URL where visitors can learn more or access the offer"
    )
    is_exclusive = models.BooleanField(
        default=False,
        help_text="Mark as exclusive to the Fend network"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this promotion is currently active"
    )
    
    # Order for display
    display_order = models.PositiveIntegerField(
        default=0,
        help_text="Order in which this promotion appears (lower numbers first)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', '-created_at']
        verbose_name = "Partner Promotion"
        verbose_name_plural = "Partner Promotions"

    def __str__(self):
        return f"{self.organization.name} - {self.title}"

    def clean(self):
        super().clean()
        
        # Limit number of promotions per organization
        if not self.pk and hasattr(self, 'organization') and self.organization:
            existing_count = PartnerPromotion.objects.filter(
                organization=self.organization,
                is_active=True
            ).count()
            if existing_count >= 5:  # Max 5 active promotions
                raise ValidationError("Maximum 5 active promotions allowed per organization")


class PilotDefinition(models.Model):
    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name='pilot_definition'
    )
    
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Provide a detailed description of the pilot"
    )
    
    # Technical Specifications
    technical_specs_doc = models.FileField(
        upload_to='pilot_specs/',
        null=True,
        blank=True
    )
    
    # Performance Metrics
    performance_metrics = models.TextField(
        null=True,
        blank=True,
        help_text="Define quantifiable performance metrics and KPIs"
    )
    
    # Compliance Requirements
    compliance_requirements = models.TextField(
        null=True,
        blank=True,
        help_text="Specify explicit compliance requirements for production launch"
    )
    
    is_private = models.BooleanField(
        default=False,
        help_text="Make this pilot definition private"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Pilot Definition for {self.organization.name}"


@receiver(post_save, sender=Organization)
def create_stripe_customer(sender, instance, created, **kwargs):
    """Create a Stripe customer when a new organization is created"""
    if created and not instance.stripe_customer_id:
        try:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            # Find a user associated with this organization
            user = instance.users.first()
            
            if user:
                customer = stripe.Customer.create(
                    email=user.email,
                    name=instance.name,
                    metadata={
                        'organization_id': instance.id,
                        'organization_type': instance.type
                    }
                )
                
                instance.stripe_customer_id = customer.id
                instance.save(update_fields=['stripe_customer_id'])
        except Exception as e:
            print(f"Error creating Stripe customer: {e}")


class UserOnboardingProgress(models.Model):
    """
    Track user onboarding progress with subtle, dismissible suggestions.
    Focus on value-driven outcomes, not feature completion.
    """
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='onboarding_progress'
    )
    
    # Profile completion milestones
    profile_logo_added = models.BooleanField(default=False)
    profile_description_added = models.BooleanField(default=False)
    team_members_added = models.BooleanField(default=False)
    
    # Engagement milestones  
    first_pilot_posted = models.BooleanField(default=False)
    first_bid_made = models.BooleanField(default=False)
    first_connection_made = models.BooleanField(default=False)
    
    # Discovery optimization
    tags_added = models.BooleanField(default=False)
    case_studies_added = models.BooleanField(default=False)
    
    # Dismissal preferences (user can hide specific suggestions)
    dismissed_suggestions = models.JSONField(default=list, blank=True)
    
    # Global onboarding preferences
    onboarding_disabled = models.BooleanField(default=False, help_text="User chose to disable all onboarding suggestions")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'organizations_user_onboarding_progress'
        verbose_name = 'User Onboarding Progress'
        verbose_name_plural = 'User Onboarding Progress'
    
    def __str__(self):
        return f"{self.user.username} - Onboarding Progress"
    
    def get_completion_percentage(self):
        """Calculate completion percentage based on user type"""
        organization = getattr(self.user, 'organization', None)
        if not organization:
            return 0
            
        if organization.type == 'startup':
            return self._get_startup_completion()
        else:
            return self._get_enterprise_completion()
    
    def _get_startup_completion(self):
        """Startup-specific completion milestones - streamlined for quick onboarding"""
        # Focus on just the essentials for quick value
        core_milestones = [
            self.profile_description_added,  # Most important for credibility
            self.first_pilot_posted or self.first_bid_made,  # Core engagement
        ]
        
        # Bonus milestones give extra completion but aren't required for 100%
        bonus_milestones = [
            self.profile_logo_added,
            self.tags_added,
        ]
        
        core_completed = sum(core_milestones)
        bonus_completed = sum(bonus_milestones)
        
        # Core milestones = 80%, bonus = 20%
        core_percentage = (core_completed / len(core_milestones)) * 80
        bonus_percentage = (bonus_completed / len(bonus_milestones)) * 20
        
        return min(100, core_percentage + bonus_percentage)
    
    def _get_enterprise_completion(self):
        """Enterprise-specific completion milestones - streamlined for quick onboarding"""
        # Focus on just the essentials for quick value
        core_milestones = [
            self.profile_description_added,  # Most important for credibility
            self.first_pilot_posted,  # Core engagement for enterprises
        ]
        
        # Bonus milestones give extra completion but aren't required for 100%
        bonus_milestones = [
            self.profile_logo_added,
            self.team_members_added,
        ]
        
        core_completed = sum(core_milestones)
        bonus_completed = sum(bonus_milestones)
        
        # Core milestones = 80%, bonus = 20%
        core_percentage = (core_completed / len(core_milestones)) * 80
        bonus_percentage = (bonus_completed / len(bonus_milestones)) * 20
        
        return min(100, core_percentage + bonus_percentage)
    
    def get_next_suggestion(self):
        """
        Get the next most valuable suggestion for the user.
        Returns None if onboarding is complete or disabled.
        """
        if self.onboarding_disabled:
            return None
            
        organization = getattr(self.user, 'organization', None)
        if not organization:
            return None
        
        # Check what's most important next
        suggestions = self._get_prioritized_suggestions(organization.type)
        
        # Filter out dismissed suggestions
        for suggestion in suggestions:
            if suggestion['id'] not in self.dismissed_suggestions:
                return suggestion
        
        return None
    
    def should_show_progress_bar(self):
        """
        Check if the progress bar should be shown at all.
        Returns False if user has dismissed the progress bar or has no suggestions.
        """
        if self.onboarding_disabled:
            return False
        
        # If user dismissed the progress bar entirely, don't show it
        if 'progress_bar' in self.dismissed_suggestions:
            return False
            
        # Only show if there are available suggestions
        return self.get_next_suggestion() is not None
    
    def dismiss_progress_bar(self):
        """Dismiss the entire progress bar"""
        if 'progress_bar' not in self.dismissed_suggestions:
            self.dismissed_suggestions.append('progress_bar')
            self.save(update_fields=['dismissed_suggestions'])
    
    def _get_prioritized_suggestions(self, org_type):
        """Get prioritized list of suggestions - streamlined for quick onboarding"""
        suggestions = []
        
        # CORE: Essential for credibility (Priority 1)
        if not self.profile_description_added:
            suggestions.append({
                'id': 'add_description', 
                'title': 'Complete your organization profile',
                'description': 'Add your company description, location, and key details so partners can find and understand your business',
                'action_text': 'Edit Profile →',
                'action_url': 'organizations:profile_edit',
                'estimated_time': '3 min',
                'priority': 1,
                'icon': 'building'
            })
        
        # CORE: Start using the platform (Priority 2)
        if org_type == 'startup':
            if not (self.first_pilot_posted or self.first_bid_made):
                suggestions.append({
                    'id': 'first_engagement',
                    'title': 'Start earning revenue',
                    'description': 'Browse active pilot opportunities from enterprises looking for startup solutions',
                    'action_text': 'Browse Pilots →',
                    'action_url': 'pilots:list',
                    'estimated_time': '5 min',
                    'priority': 2,
                    'icon': 'search'
                })
        elif org_type == 'enterprise':
            if not self.first_pilot_posted:
                suggestions.append({
                    'id': 'post_first_pilot',
                    'title': 'Find innovation partners',
                    'description': 'Post your first pilot project to connect with innovative startups and get bids on your challenges',
                    'action_text': 'Create Pilot →',
                    'action_url': 'pilots:create',
                    'estimated_time': '8 min',
                    'priority': 2,
                    'icon': 'plus'
                })
        
        # BONUS: Polish your presence (Priority 3) - only after core is done
        if self.profile_description_added and not self.profile_logo_added:
            suggestions.append({
                'id': 'add_logo',
                'title': 'Upload your company logo',
                'description': 'Professional branding helps build trust and makes your organization more recognizable',
                'action_text': 'Upload Logo →',
                'action_url': 'organizations:profile_edit',
                'estimated_time': '2 min',
                'priority': 3,
                'icon': 'upload'
            })
        
        # BONUS: Optimization features (Priority 4) - only after engagement
        engaged = (self.first_pilot_posted or self.first_bid_made)
        
        # BONUS: Team building (Priority 4) - enterprise specific
        if engaged and org_type == 'enterprise' and not self.team_members_added:
            suggestions.append({
                'id': 'add_team',
                'title': 'Add your team members',
                'description': 'Invite team members to collaborate on pilot projects and manage your organization together',
                'action_text': 'Invite Team →',
                'action_url': 'organizations:profile_edit',
                'estimated_time': '5 min',
                'priority': 4,
                'icon': 'plus'
            })
        
        # BONUS: Optimization features (Priority 4) - startup specific
        if engaged and org_type == 'startup' and not self.tags_added:
            suggestions.append({
                'id': 'add_tags',
                'title': 'Add your expertise areas',
                'description': 'Tag your skills and industry expertise to get matched with more relevant opportunities',
                'action_text': 'Add Expertise →',
                'action_url': 'organizations:profile_edit',
                'estimated_time': '2 min',
                'priority': 4,
                'icon': 'tag'
            })
        
        # Sort by priority
        return sorted(suggestions, key=lambda x: x['priority'])
    
    def dismiss_suggestion(self, suggestion_id):
        """Dismiss a specific suggestion"""
        if suggestion_id not in self.dismissed_suggestions:
            self.dismissed_suggestions.append(suggestion_id)
            self.save(update_fields=['dismissed_suggestions'])
    
    def disable_all_onboarding(self):
        """User chooses to disable all onboarding suggestions"""
        self.onboarding_disabled = True
        self.save(update_fields=['onboarding_disabled'])
    
    def update_milestone(self, milestone_name, completed=True):
        """Update a specific milestone"""
        if hasattr(self, milestone_name):
            setattr(self, milestone_name, completed)
            self.save(update_fields=[milestone_name])
    
    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create onboarding progress for a user"""
        progress, created = cls.objects.get_or_create(user=user)
        # Always refresh progress detection to catch recently completed tasks
        progress._detect_existing_progress()
        return progress
    
    def _detect_existing_progress(self):
        """Detect progress that user may have already made"""
        organization = getattr(self.user, 'organization', None)
        if not organization:
            return
        
        # Check if logo exists
        if organization.logo:
            self.profile_logo_added = True
        
        # Check if profile is substantially complete (description + at least 2 other key fields)
        profile_fields_completed = 0
        
        # Core field: Description (required)
        has_description = organization.description and len(organization.description.strip()) > 50
        
        # Additional profile fields
        if has_description:
            profile_fields_completed += 1
            
        if organization.industry_tags and len(organization.industry_tags) > 0:
            profile_fields_completed += 1
            
        if organization.employee_count:
            profile_fields_completed += 1
            
        if organization.headquarters_location:
            profile_fields_completed += 1
            
        if organization.founding_year:
            profile_fields_completed += 1
            
        if organization.linkedin_url or organization.twitter_url:
            profile_fields_completed += 1
        
        # Consider profile complete if they have description + at least 2 other fields
        if profile_fields_completed >= 3:
            self.profile_description_added = True
        
        # Check if they've posted pilots
        from apps.pilots.models import Pilot
        if Pilot.objects.filter(organization=organization).exists():
            self.first_pilot_posted = True
        
        # Check if they've made bids
        from apps.pilots.models import PilotBid
        if PilotBid.objects.filter(startup=organization).exists():
            self.first_bid_made = True
        
        # Save detected progress
        self.save()