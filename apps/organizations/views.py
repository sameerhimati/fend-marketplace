from django.views.generic import CreateView, UpdateView, TemplateView, ListView, DetailView, DeleteView
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.db import transaction
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Organization, PilotDefinition, PartnerPromotion
from .forms import (
    OrganizationBasicForm, PilotDefinitionForm, EnhancedOrganizationProfileForm, 
    PartnerPromotionForm
)
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.pilots.models import Pilot, PilotBid
from apps.users.models import User
from django.views import View
from apps.notifications.services import create_notification
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from django.db.models import Case, When, IntegerField, Q
from random import shuffle
import json
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST

class OrganizationRegistrationView(CreateView):
    model = Organization
    form_class = OrganizationBasicForm
    template_name = 'organizations/registration/basic.html'
    
    @method_decorator(ensure_csrf_cookie)
    def dispatch(self, request, *args, **kwargs):
        # Ensure session exists before processing
        if not request.session.session_key:
            request.session.create()
        return super().dispatch(request, *args, **kwargs)
    
    def get_initial(self):
        """Pre-populate form with session data if available"""
        initial = super().get_initial()
        reg_data = self.request.session.get('registration_data', {})
        
        if reg_data:
            initial.update({
                'name': reg_data.get('organization_name', ''),
                'type': reg_data.get('organization_type', ''),
                'website': reg_data.get('organization_website', ''),
                'email': reg_data.get('email', ''),
            })
            
        return initial
    
    
    @transaction.atomic
    def form_valid(self, form):
        try:
            # Create organization with pending approval status
            organization = form.save(commit=False)
            organization.approval_status = 'pending'
            organization.save()
            
            # Handle legal document acceptances
            current_time = timezone.now()
            
            # Accept required legal documents based on form checkboxes
            if self.request.POST.get('accept_terms'):
                organization.terms_of_service_accepted = True
                organization.terms_of_service_accepted_at = current_time
            
            if self.request.POST.get('accept_privacy'):
                organization.privacy_policy_accepted = True
                organization.privacy_policy_accepted_at = current_time
                
            if self.request.POST.get('accept_user_agreement'):
                organization.user_agreement_accepted = True
                organization.user_agreement_accepted_at = current_time
            
            # Auto-accept Data Processing Agreement for EU users
            if organization.is_eu_based():
                organization.data_processing_agreement_accepted = True
                organization.data_processing_agreement_accepted_at = current_time
            
            organization.save()
            
            # Create user with default verification (now True)
            user = User.objects.create_user(
                username=form.cleaned_data['email'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password']
            )
            
            # Link user to organization
            user.organization = organization
            user.save()
            
            # Log the user in
            auth_login(self.request, user)
            
            # Redirect to payment selection
            return redirect('payments:payment_selection')
            
        except Exception as e:
            print(f"Error in form_valid: {e}")
            messages.error(self.request, "Error creating organization. Please try again.")
            return self.form_invalid(form)
    
    def post(self, request, *args, **kwargs):
        if 'back' in request.POST:
            return redirect('landing')  # Go back to landing page
        return super().post(request, *args, **kwargs)
            
    def form_invalid(self, form):
        print(f"Form errors: {form.errors}")  # Debug log
        return super().form_invalid(form)

class PendingApprovalView(LoginRequiredMixin, TemplateView):
    template_name = 'organizations/pending_approval.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Check if user has an active subscription
        has_subscription = False
        if hasattr(self.request.user.organization, 'has_active_subscription'):
            has_subscription = self.request.user.organization.has_active_subscription()
        
        context['has_subscription'] = has_subscription
        return context

@login_required
def remove_logo(request):
    """Remove the organization's logo"""
    if request.method != 'GET':
        return redirect('organizations:profile_edit')
    
    organization = request.user.organization
    
    # Delete the logo file
    if organization.logo:
        import os
        if os.path.isfile(organization.logo.path):
            os.remove(organization.logo.path)
        organization.logo = None
        organization.save()
        
        messages.success(request, "Logo removed successfully")
    
    return redirect('organizations:profile_edit')

class RegistrationCompleteView(LoginRequiredMixin, TemplateView):
    template_name = 'organizations/registration/complete.html'
    
    def get(self, request, *args, **kwargs):
        # Check if the user has completed payment
        if not request.user.organization.has_active_subscription():
            # Redirect to payment selection
            return redirect('payments:payment_selection')
        
        # If payment is complete, show completion page
        response = super().get(request, *args, **kwargs)
        response['Refresh'] = '3;url=' + reverse('organizations:dashboard')
        return response

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'organizations/dashboard/dashboard.html'
    
    def get(self, request, *args, **kwargs):
        # Redirect to type-specific dashboard based on organization type
        if not hasattr(request.user, 'organization') or request.user.organization is None:
            # Simply redirect to login for users without organizations
            messages.error(request, "Your account needs to be properly set up.")
            return redirect('organizations:login')
            
        if request.user.organization.type == 'enterprise':
            return redirect('organizations:enterprise_dashboard')
        return redirect('organizations:startup_dashboard')

def get_featured_promotions(user_organization_type, exclude_org_id=None, limit=3):
    """
    Get 'featured' partner promotions for dashboard display
    
    Algorithm:
    1. Recent promotions get priority (last 30 days)
    2. Max 2 promotions per organization 
    3. Mix of enterprise/startup promotions
    4. Manual curation via display_order
    5. Active promotions only
    
    Args:
        user_organization_type: 'enterprise' or 'startup'
        exclude_org_id: Current user's org ID to exclude
        limit: Max promotions to return
    """
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    # Base queryset - active promotions only
    base_qs = PartnerPromotion.objects.filter(
        is_active=True,
        organization__approval_status='approved'
    ).select_related('organization')
    
    # Exclude current user's organization
    if exclude_org_id:
        base_qs = base_qs.exclude(organization_id=exclude_org_id)
    
    # Prioritize different types based on user type
    if user_organization_type == 'enterprise':
        # Enterprises see startup promotions first (solutions/tools)
        priority_orgs = base_qs.filter(organization__type='startup')
        secondary_orgs = base_qs.filter(organization__type='enterprise')
    else:
        # Startups see enterprise promotions first (opportunities)
        priority_orgs = base_qs.filter(organization__type='enterprise') 
        secondary_orgs = base_qs.filter(organization__type='startup')
    
    # Add recency scoring
    def add_recency_score(queryset):
        return queryset.annotate(
            recency_score=Case(
                When(created_at__gte=thirty_days_ago, then=10),  # Recent = high score
                When(created_at__gte=timezone.now() - timedelta(days=60), then=5),
                default=1,
                output_field=IntegerField()
            )
        ).order_by('-recency_score', 'display_order', '-created_at')
    
    priority_promotions = add_recency_score(priority_orgs)
    secondary_promotions = add_recency_score(secondary_orgs)
    
    # Limit to max 2 per organization and collect results
    featured_promotions = []
    org_count = {}
    
    # First pass: Priority type (startups for enterprises, enterprises for startups)
    for promo in priority_promotions:
        org_id = promo.organization_id
        if org_count.get(org_id, 0) < 2 and len(featured_promotions) < limit:
            featured_promotions.append(promo)
            org_count[org_id] = org_count.get(org_id, 0) + 1
    
    # Second pass: Secondary type if we need more
    for promo in secondary_promotions:
        org_id = promo.organization_id
        if org_count.get(org_id, 0) < 2 and len(featured_promotions) < limit:
            featured_promotions.append(promo)
            org_count[org_id] = org_count.get(org_id, 0) + 1
    
    return featured_promotions[:limit]


class EnterpriseDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'organizations/dashboard/enterprise.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if not hasattr(self.request.user, 'organization') or self.request.user.organization is None:
            messages.error(self.request, "Your account is not associated with an organization.")
            return context
    
        user_org = self.request.user.organization
        
        # Check for newly approved users to show "How Fend Works" popup
        # Show popup if approved within last 24 hours and user hasn't seen it
        show_popup = False
        if (user_org.approval_status == 'approved' and 
            user_org.approval_date and 
            (timezone.now() - user_org.approval_date).total_seconds() < 86400):  # 24 hours
            # Check if user has an unread account_approved notification
            from apps.notifications.models import Notification
            has_unread_approval = Notification.objects.filter(
                recipient=self.request.user,
                type='account_approved',
                read=False
            ).exists()
            show_popup = has_unread_approval
        context['show_how_fend_works'] = show_popup
        
        # Pilot data - separate drafts from active/published pilots
        all_pilots = Pilot.objects.filter(organization=user_org).order_by('-created_at')
        context['active_pilots'] = all_pilots.filter(
            status__in=['published', 'pending_approval', 'in_progress', 'completed']
        )[:5]
        context['draft_pilots'] = all_pilots.filter(status='draft')[:5]
        
        # Network data - use deterministic ordering instead of random
        context['enterprises'] = Organization.objects.filter(
            type='enterprise',
            approval_status='approved',
            onboarding_completed=True
        ).exclude(id=user_org.id).order_by('-created_at')[:4]
        
        context['startups'] = Organization.objects.filter(
            type='startup',
            approval_status='approved',
            onboarding_completed=True
        ).order_by('-created_at')[:4]
        
        # NEW: Featured Partner Promotions
        context['featured_promotions'] = get_featured_promotions(
            user_organization_type='enterprise',
            exclude_org_id=user_org.id,
            limit=3
        )
        
        return context


class StartupDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'organizations/dashboard/startup.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if not hasattr(self.request.user, 'organization') or self.request.user.organization is None:
            messages.error(self.request, "Your account is not associated with an organization.")
            return context
    
        user_org = self.request.user.organization
        
        # Check for newly approved users to show "How Fend Works" popup
        # Show popup if approved within last 24 hours and user hasn't seen it
        show_popup = False
        if (user_org.approval_status == 'approved' and 
            user_org.approval_date and 
            (timezone.now() - user_org.approval_date).total_seconds() < 86400):  # 24 hours
            # Check if user has an unread account_approved notification
            from apps.notifications.models import Notification
            has_unread_approval = Notification.objects.filter(
                recipient=self.request.user,
                type='account_approved',
                read=False
            ).exists()
            show_popup = has_unread_approval
        context['show_how_fend_works'] = show_popup
        
        # Existing pilots data
        pilots = Pilot.objects.filter(
            status='published',
            is_private=False,
            organization__approval_status='approved'
        ).order_by('-created_at')
        
        active_bid_pilot_ids = PilotBid.objects.filter(
            startup=user_org
        ).exclude(status='declined').values_list('pilot_id', flat=True)
        
        pilots_with_approved_bids = PilotBid.objects.filter(
            status='approved'
        ).values_list('pilot_id', flat=True)
        
        excluded_pilots = set(active_bid_pilot_ids) | set(pilots_with_approved_bids)
        context['pilots'] = pilots.exclude(id__in=excluded_pilots)
        
        # Existing network data
        context['fellow_startups'] = Organization.objects.filter(
            type='startup',
            approval_status='approved',
            onboarding_completed=True
        ).exclude(id=user_org.id).order_by('-created_at')[:4]
        
        context['enterprises'] = Organization.objects.filter(
            type='enterprise',
            approval_status='approved',
            onboarding_completed=True
        ).order_by('-created_at')[:4]
        
        # NEW: Featured Partner Promotions  
        context['featured_promotions'] = get_featured_promotions(
            user_organization_type='startup',
            exclude_org_id=user_org.id,
            limit=3
        )
        
        return context
    
class CustomLoginView(LoginView):
    template_name = 'organizations/auth/login.html'
    
    def get_success_url(self):
        return reverse_lazy('organizations:dashboard')

class OrganizationProfileView(LoginRequiredMixin, DetailView):
    model = Organization
    template_name = 'organizations/profile.html'
    context_object_name = 'organization'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.object
        
        time_since_created = timezone.now() - organization.created_at
        days = time_since_created.days
        
        if days < 30:
            time_on_platform = f"{days} days"
        elif days < 365:
            months = days // 30
            time_on_platform = f"{months} month{'s' if months > 1 else ''}"
        else:
            years = days // 365
            time_on_platform = f"{years} year{'s' if years > 1 else ''}"
        
        context['time_on_platform'] = time_on_platform
        
        # Add pilot statistics for enterprises (not the actual pilots)
        if organization.type == 'enterprise':
            from apps.pilots.models import Pilot
            pilot_stats = {
                'total': Pilot.objects.filter(organization=organization).count(),
                'published': Pilot.objects.filter(
                    organization=organization,
                    status='published'
                ).count(),
                'active': Pilot.objects.filter(
                    organization=organization,
                    status__in=['published', 'in_progress']
                ).count()
            }
            context['pilot_stats'] = pilot_stats
        
        if organization.type == 'startup':
            # Get all pilots this startup has bids on
            from apps.pilots.models import PilotBid
            pilot_stats = {
                'total_pilots_completed': PilotBid.objects.filter(startup=organization, status__in=['completed']).count(),
                'current_pilots': PilotBid.objects.filter(
                    startup=organization,
                    status__in=['pending', 'under_review', 'approved', 'live']
                ).count(),
                'total_money': PilotBid.objects.filter(startup=organization, status__in=['completed']).aggregate(Sum('amount'))['amount__sum']
            }
            context['pilot_stats'] = pilot_stats
        
        # Add partner promotions (MOST IMPORTANT FEATURE)
        context['partner_promotions'] = organization.partner_promotions.filter(
            is_active=True
        ).order_by('display_order', '-created_at')
        
        # Add social media links for display
        social_links = []
        if organization.linkedin_url:
            social_links.append({
                'name': 'LinkedIn',
                'url': organization.linkedin_url,
                'icon': 'linkedin'
            })
        if organization.twitter_url:
            social_links.append({
                'name': 'Twitter',
                'url': organization.twitter_url,
                'icon': 'twitter'
            })
        context['social_links'] = social_links
        
        return context

class ProfileEditView(LoginRequiredMixin, TemplateView):
    template_name = 'organizations/profile_edit.html'
    
    def get_organization(self):
        return self.request.user.organization
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        
        if self.request.method == 'GET':
            form = EnhancedOrganizationProfileForm(instance=organization)
        else:
            form = EnhancedOrganizationProfileForm(
                data=self.request.POST, 
                files=self.request.FILES,
                instance=organization
            )
        
        context['form'] = form
        context['organization'] = organization
        return context
    
    def post(self, request, *args, **kwargs):
        print("=== POST METHOD CALLED ===")
        print(f"POST data: {request.POST}")
        print(f"FILES data: {request.FILES}")
        print(f"Content type: {request.content_type}")
        
        organization = self.get_organization()
        form = EnhancedOrganizationProfileForm(
            data=request.POST, 
            files=request.FILES,
            instance=organization
        )
        
        if form.is_valid():
            print("=== FORM VALID ===")
            print(f"Form cleaned data: {form.cleaned_data}")
            
            # Manually update the organization
            for field_name, value in form.cleaned_data.items():
                if hasattr(organization, field_name) and value is not None:
                    setattr(organization, field_name, value)
            
            # Save without calling full_clean()
            organization.save(update_fields=list(form.cleaned_data.keys()))
            
            messages.success(request, "Profile updated successfully!")
            return redirect('organizations:profile', pk=organization.pk)
        else:
            print("=== FORM INVALID ===")
            print(f"Form errors: {form.errors}")
            messages.error(request, "Please correct the errors below.")
        
        # If form is invalid, return the context with errors
        return self.render_to_response(self.get_context_data())


# =============================================================================
# PARTNER PROMOTION VIEWS
# =============================================================================

class PartnerPromotionListView(LoginRequiredMixin, ListView):
    """View to list and manage partner promotions"""
    model = PartnerPromotion
    template_name = 'organizations/promotions/promo_list.html'
    context_object_name = 'promotions'
    
    def get_queryset(self):
        return PartnerPromotion.objects.filter(
            organization=self.request.user.organization
        ).order_by('display_order', '-created_at')

class PartnerPromotionCreateView(LoginRequiredMixin, CreateView):
    """View to create new partner promotions"""
    model = PartnerPromotion
    form_class = PartnerPromotionForm
    template_name = 'organizations/promotions/promo_form.html'

    def get_form(self, form_class=None):
        """Set the organization on the form instance before validation"""
        form = super().get_form(form_class)
        form.instance.organization = self.request.user.organization
        return form
    
    def form_valid(self, form):
        # Check promotion limit
        existing_count = PartnerPromotion.objects.filter(
            organization=self.request.user.organization,
            is_active=True
        ).count()
        
        if existing_count >= 5:
            messages.error(self.request, "You can only have up to 5 active promotions.")
            return self.form_invalid(form)
        
        messages.success(self.request, "Partner promotion created successfully!")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('organizations:partner_promotions_list')

class PartnerPromotionUpdateView(LoginRequiredMixin, UpdateView):
    """View to edit partner promotions"""
    model = PartnerPromotion
    form_class = PartnerPromotionForm
    template_name = 'organizations/promotions/promo_form.html'
    
    def get_queryset(self):
        # Only allow editing own organization's promotions
        return PartnerPromotion.objects.filter(
            organization=self.request.user.organization
        )
    
    def form_valid(self, form):
        messages.success(self.request, "Partner promotion updated successfully!")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('organizations:partner_promotions_list')

class PartnerPromotionDeleteView(LoginRequiredMixin, DeleteView):
    """View to delete partner promotions"""
    model = PartnerPromotion
    template_name = 'organizations/promotions/promo_delete.html'
    
    def get_queryset(self):
        # Only allow deleting own organization's promotions
        return PartnerPromotion.objects.filter(
            organization=self.request.user.organization
        )
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, "Partner promotion deleted successfully!")
        return super().delete(request, *args, **kwargs)
    
    def get_success_url(self):
        return reverse('organizations:partner_promotions_list')


# =============================================================================
# ADMIN VIEWS - Organization Approval Workflow
# =============================================================================

@login_required
@staff_member_required
def admin_pending_approvals(request):
    """Admin view for organization approvals with bulk actions"""
    if request.method == 'POST':
        action = request.POST.get('action')
        org_ids = request.POST.getlist('org_ids')
        
        # Handle single organization approval/rejection
        single_org_id = request.POST.get('single_org_id')
        if single_org_id and action:
            org_ids = [single_org_id]
        
        if org_ids and action:
            organizations = Organization.objects.filter(id__in=org_ids)
            
            if action == 'approve':
                count = 0
                for org in organizations:
                    org.approval_status = 'approved'
                    org.approval_date = timezone.now()
                    org.save()
                    
                    # Create notification for all organization users
                    for user in org.users.all():
                        create_notification(
                            recipient=user,
                            notification_type='account_approved',
                            title="Account Approved!",
                            message=f"Your {org.get_type_display()} account has been approved. You now have full access to Fend Marketplace."
                        )
                    count += 1
                
                messages.success(request, f'{count} organizations were approved successfully.')
                
            elif action == 'reject':
                rejection_reason = request.POST.get('rejection_reason', '')
                count = 0
                for org in organizations:
                    org.approval_status = 'rejected'
                    org.save()
                    
                    # Create notification for all organization users
                    for user in org.users.all():
                        create_notification(
                            recipient=user,
                            notification_type='account_rejected',
                            title="Account Requires Additional Information",
                            message=f"Your {org.get_type_display()} account needs additional information before approval. Reason: {rejection_reason}"
                        )
                    count += 1
                
                messages.success(request, f'{count} organizations were rejected.')
    
    # Get all organizations with pending approval status
    pending_orgs = Organization.objects.filter(
        approval_status='pending'
    ).select_related().order_by('-created_at')
    
    context = {
        'title': 'Organization Approvals',
        'pending_orgs': pending_orgs,
    }
    return render(request, 'admin/organizations/pending_approvals.html', context)

@login_required
@staff_member_required
def admin_organization_detail(request, org_id):
    """Admin view for individual organization review"""
    organization = get_object_or_404(Organization, id=org_id)
    
    context = {
        'title': f'Review {organization.name}',
        'organization': organization,
    }
    return render(request, 'admin/organizations/approval_detail.html', context)

@login_required
@staff_member_required
def admin_approve_organization(request, org_id):
    """Admin action to approve a single organization"""
    if request.method != 'POST':
        return redirect('admin:organizations_organization_changelist')
    
    organization = get_object_or_404(Organization, id=org_id)
    
    # Approve the organization
    organization.approval_status = 'approved'
    organization.approval_date = timezone.now()
    organization.save()
    
    # Create notification for all organization users
    for user in organization.users.all():
        create_notification(
            recipient=user,
            notification_type='account_approved',
            title="Account Approved!",
            message=f"Your {organization.get_type_display()} account has been approved. You now have full access to Fend Marketplace."
        )
    
    messages.success(request, f"{organization.name} has been approved successfully.")
    return redirect('admin:pending_approvals')

@login_required
@staff_member_required
def admin_reject_organization(request, org_id):
    """Admin action to reject a single organization"""
    if request.method != 'POST':
        return redirect('admin:organizations_organization_changelist')
    
    organization = get_object_or_404(Organization, id=org_id)
    rejection_reason = request.POST.get('rejection_reason', '')
    
    # Reject the organization
    organization.approval_status = 'rejected'
    organization.save()
    
    # Create notification for all organization users
    for user in organization.users.all():
        create_notification(
            recipient=user,
            notification_type='account_rejected',
            title="Account Requires Additional Information",
            message=f"Your {organization.get_type_display()} account needs additional information before approval. Reason: {rejection_reason}"
        )
    
    messages.success(request, f"{organization.name} has been rejected with feedback.")
    return redirect('admin:pending_approvals')

class DirectoryView(LoginRequiredMixin, TemplateView):
    """
    Unified view that displays both enterprises and startups in a single interface
    with filtering, search, and tabbed navigation.
    """
    template_name = 'organizations/directory.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if not hasattr(self.request.user, 'organization') or self.request.user.organization is None:
            context['enterprises'] = Organization.objects.none()
            context['startups'] = Organization.objects.none()
            return context
        
        # Get search query and filters from request
        search_query = self.request.GET.get('search', '').strip()
        org_type_filter = self.request.GET.get('type', '')  # 'enterprise', 'startup', or empty for all
        
        # Base queryset - approved organizations except current user's
        base_queryset = Organization.objects.filter(
            approval_status='approved',
            onboarding_completed=True
        ).exclude(
            id=self.request.user.organization.id
        ).order_by('name')
        
        # Apply search if provided
        if search_query:
            base_queryset = base_queryset.filter(
                Q(name__icontains=search_query) |
                Q(website__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        # Get enterprises and startups
        if org_type_filter == 'enterprise':
            enterprises = base_queryset.filter(type='enterprise')
            startups = Organization.objects.none()
        elif org_type_filter == 'startup':
            enterprises = Organization.objects.none()
            startups = base_queryset.filter(type='startup')
        else:
            # Show both types
            enterprises = base_queryset.filter(type='enterprise')
            startups = base_queryset.filter(type='startup')
        
        # Add pagination if needed
        from django.core.paginator import Paginator
        
        # Paginate enterprises
        enterprise_paginator = Paginator(enterprises, 12)  # 12 per page
        enterprise_page = self.request.GET.get('enterprise_page', 1)
        enterprises_paginated = enterprise_paginator.get_page(enterprise_page)
        
        # Paginate startups
        startup_paginator = Paginator(startups, 12)  # 12 per page
        startup_page = self.request.GET.get('startup_page', 1)
        startups_paginated = startup_paginator.get_page(startup_page)
        
        context.update({
            'enterprises': enterprises_paginated,
            'startups': startups_paginated,
            'search_query': search_query,
            'org_type_filter': org_type_filter,
            'total_enterprises': enterprises.count() if hasattr(enterprises, 'count') else 0,
            'total_startups': startups.count() if hasattr(startups, 'count') else 0,
        })
        
        return context


@csrf_exempt
@require_POST
def track_promotion_click(request):
    """
    Track promotion clicks for analytics
    Optional endpoint - you can remove if not needed
    """
    try:
        data = json.loads(request.body)
        promotion_id = data.get('promotion_id')
        organization_name = data.get('organization_name')
        source = data.get('source', 'unknown')
        
        print(f"Promotion click: {promotion_id} from {organization_name} via {source}")
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
    

class DealsView(LoginRequiredMixin, TemplateView):
    """
    Dedicated page for browsing all Fend partner deals and exclusive offers
    """
    template_name = 'organizations/deals.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if not hasattr(self.request.user, 'organization') or self.request.user.organization is None:
            context['deals'] = PartnerPromotion.objects.none()
            return context
        
        user_org = self.request.user.organization
        
        # Get search and filter parameters
        search_query = self.request.GET.get('search', '').strip()
        org_type_filter = self.request.GET.get('org_type', '')  # 'enterprise', 'startup', or empty
        deal_type_filter = self.request.GET.get('deal_type', '')  # 'exclusive', 'standard', or empty
        sort_by = self.request.GET.get('sort', 'recent')  # 'recent', 'popular', 'title'
        
        # Base queryset - active promotions from approved organizations, exclude current user's org
        deals_queryset = PartnerPromotion.objects.filter(
            is_active=True,
            organization__approval_status='approved'
        ).exclude(
            organization_id=user_org.id
        ).select_related('organization')
        
        # Apply search filter
        if search_query:
            deals_queryset = deals_queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(organization__name__icontains=search_query)
            )
        
        # Apply organization type filter
        if org_type_filter:
            deals_queryset = deals_queryset.filter(organization__type=org_type_filter)
        
        # Apply deal type filter
        if deal_type_filter == 'exclusive':
            deals_queryset = deals_queryset.filter(is_exclusive=True)
        elif deal_type_filter == 'standard':
            deals_queryset = deals_queryset.filter(is_exclusive=False)
        
        # Apply sorting
        if sort_by == 'recent':
            deals_queryset = deals_queryset.order_by('-created_at')
        elif sort_by == 'popular':
            # You could add a click_count field later for real popularity
            deals_queryset = deals_queryset.order_by('-created_at')  # Fallback to recent for now
        elif sort_by == 'title':
            deals_queryset = deals_queryset.order_by('title')
        else:
            deals_queryset = deals_queryset.order_by('display_order', '-created_at')
        
        # Pagination
        from django.core.paginator import Paginator
        paginator = Paginator(deals_queryset, 12)  # 12 deals per page
        page_number = self.request.GET.get('page', 1)
        deals_page = paginator.get_page(page_number)
        
        # Get statistics for the header
        total_deals = deals_queryset.count()
        exclusive_count = deals_queryset.filter(is_exclusive=True).count()
        standard_count = deals_queryset.filter(is_exclusive=False).count()
        
        # Get featured deals for the hero section (top 3 most recent)
        featured_deals = get_featured_promotions(
            user_organization_type=user_org.type,
            exclude_org_id=user_org.id,
            limit=3
        )
        
        context.update({
            'deals': deals_page,
            'featured_deals': featured_deals,
            'search_query': search_query,
            'org_type_filter': org_type_filter,
            'deal_type_filter': deal_type_filter,
            'sort_by': sort_by,
            'total_deals': total_deals,
            'exclusive_count': exclusive_count,
            'standard_count': standard_count,
        })
        
        return context