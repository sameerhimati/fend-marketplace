from django.views.generic import CreateView, UpdateView, TemplateView, ListView, DetailView
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.contrib.auth import login as auth_login, get_user_model
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Organization, PilotDefinition
from .forms import OrganizationBasicForm, PilotDefinitionForm, OrganizationProfileForm
from django.views.generic import TemplateView
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.pilots.models import Pilot, PilotBid
from apps.users.models import User
from django.urls import reverse
from django.views import View
from apps.notifications.services import create_notification

class OrganizationRegistrationView(CreateView):
    model = Organization
    form_class = OrganizationBasicForm
    template_name = 'organizations/registration/basic.html'
    
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

class EnterpriseDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'organizations/dashboard/enterprise.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if not hasattr(self.request.user, 'organization') or self.request.user.organization is None:
            messages.error(self.request, "Your account is not associated with an organization.")
            return context
    
        user_org = self.request.user.organization
        
        # Get all pilots for this enterprise
        context['active_pilots'] = Pilot.objects.filter(
            organization=user_org
        ).order_by('-created_at')[:5]  # Get 5 most recent pilots
        
        # Get other enterprises for display
        context['enterprises'] = Organization.objects.filter(
            type='enterprise',
            approval_status='approved',
            onboarding_completed=True
        ).exclude(
            id=user_org.id
        ).order_by('?')[:4]  # Random selection of 4 other enterprises
        
        # Get startups for display
        context['startups'] = Organization.objects.filter(
            type='startup',
            approval_status='approved',
            onboarding_completed=True
        ).order_by('?')[:4]  # Random selection of 4 startups
        
        return context

class StartupDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'organizations/dashboard/startup.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if not hasattr(self.request.user, 'organization') or self.request.user.organization is None:
            messages.error(self.request, "Your account is not associated with an organization.")
            return context
    
        user_org = self.request.user.organization
        
        # Get available pilots for startups
        pilots = Pilot.objects.filter(
            status='published',
            is_private=False,
            organization__approval_status='approved'  # Only show pilots from approved organizations
        ).order_by('-created_at')
        
        # Exclude pilots where this startup already has an active bid
        active_bid_pilot_ids = PilotBid.objects.filter(
            startup=user_org
        ).exclude(
            status='declined'
        ).values_list('pilot_id', flat=True)
        
        # Exclude pilots that already have any approved bid
        pilots_with_approved_bids = PilotBid.objects.filter(
            status='approved'
        ).values_list('pilot_id', flat=True)
        
        # Create a set of all pilots to exclude
        excluded_pilots = set(active_bid_pilot_ids) | set(pilots_with_approved_bids)
        
        # Apply exclusions
        context['pilots'] = pilots.exclude(id__in=excluded_pilots)
        
        # Get fellow startups for the network section - exclude current startup
        context['fellow_startups'] = Organization.objects.filter(
            type='startup',
            approval_status='approved',
            onboarding_completed=True
        ).exclude(
            id=user_org.id
        ).order_by('?')[:4]  # Random selection of 4 other startups
        
        # Get enterprise partners - alphabetical order
        context['enterprises'] = Organization.objects.filter(
            type='enterprise',
            approval_status='approved',
            onboarding_completed=True
        ).order_by('?')[:4]  # Random selection of 4 enterprises
        
        return context
    
class CustomLoginView(LoginView):
    template_name = 'organizations/auth/login.html'
    
    def get_success_url(self):
        return reverse_lazy('organizations:dashboard')
    
class EnterpriseDirectoryView(LoginRequiredMixin, ListView):
    model = Organization
    template_name = 'organizations/enterprise_directory.html'
    context_object_name = 'enterprises'
    
    def get_queryset(self):
        if not hasattr(self.request.user, 'organization') or self.request.user.organization is None:
            return Organization.objects.none() 
        # Show only approved enterprises except the current user's organization
        return Organization.objects.filter(
            type='enterprise',
            approval_status='approved',
            onboarding_completed=True
        ).exclude(
            id=self.request.user.organization.id
        ).order_by('name')

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
        
        return context

class ProfileEditView(LoginRequiredMixin, UpdateView):
    model = Organization
    form_class = OrganizationProfileForm
    template_name = 'organizations/profile_edit.html'
    
    def get_object(self, queryset=None):
        # Only allow editing own organization
        return self.request.user.organization
    
    def get_success_url(self):
        return reverse('organizations:profile', kwargs={'pk': self.object.pk})

class StartupDirectoryView(LoginRequiredMixin, ListView):
    model = Organization
    template_name = 'organizations/startup_directory.html'
    context_object_name = 'startups'
    
    def get_queryset(self):
        if not hasattr(self.request.user, 'organization') or self.request.user.organization is None:
            return Organization.objects.none() 
        # Show only approved startups except the current user's organization
        return Organization.objects.filter(
            type='startup',
            approval_status='approved',
            onboarding_completed=True
        ).exclude(
            id=self.request.user.organization.id
        ).order_by('name')

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