from django.views.generic import CreateView, UpdateView, TemplateView, ListView, DetailView
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.contrib.auth import login, get_user_model
from django.db import transaction
from .models import Organization, PilotDefinition
from .forms import OrganizationBasicForm, EnterpriseDetailsForm, PilotDefinitionForm, OrganizationProfileForm
from django.views.generic import TemplateView
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.pilots.models import Pilot, PilotBid

User = get_user_model()

class OrganizationRegistrationView(CreateView):
    model = Organization
    form_class = OrganizationBasicForm
    template_name = 'organizations/registration/basic.html'
    
    @transaction.atomic
    def form_valid(self, form):
        try:
            # Create organization without saving to DB yet
            organization = form.save(commit=False)
            
            # Store registration data in session
            self.request.session['registration_data'] = {
                'organization_name': organization.name,
                'organization_type': organization.type,
                'organization_website': organization.website,
                'email': form.cleaned_data['email'],
                'password': form.cleaned_data['password'],
            }
            
            # Store the organization in the database without finalizing
            organization.save()
            self.request.session['organization_id'] = organization.id
            
            if organization.type == 'enterprise':
                organization.add_tokens(1)
                return redirect('organizations:enterprise_details', pk=organization.pk)
            
            # For startups, complete registration
            return self.complete_registration(organization)
            
        except Exception as e:
            print(f"Error in form_valid: {e}")
            messages.error(self.request, "Error creating organization. Please try again.")
            return self.form_invalid(form)
    
    def complete_registration(self, organization=None):
        """Complete the registration process by creating user and finalizing organization"""
        reg_data = self.request.session.get('registration_data', {})
        
        if not organization and 'organization_id' in self.request.session:
            organization = get_object_or_404(Organization, pk=self.request.session['organization_id'])
        
        if not organization or not reg_data:
            messages.error(self.request, "Registration data is missing. Please start over.")
            return redirect('organizations:register')
        
        try:
            # Create user
            user = User.objects.create_user(
                username=reg_data['email'],
                email=reg_data['email'],
                password=reg_data['password']
            )
            
            # Link user to organization
            user.organization = organization
            user.save()
            
            # Mark organization as complete
            organization.onboarding_completed = True
            organization.save()
            
            # Clean up session
            if 'registration_data' in self.request.session:
                del self.request.session['registration_data']
            if 'organization_id' in self.request.session:
                del self.request.session['organization_id']
                
            # Log the user in now that registration is complete
            login(self.request, user)
            
            # Redirect to completion page
            return redirect('payments:payment_selection')
        
        except Exception as e:
            print(f"Error completing registration: {e}")
            messages.error(self.request, "Error creating user account. Please try again.")
            if organization:
                organization.delete()  # Clean up partial registration
            return redirect('organizations:register')
    
    def post(self, request, *args, **kwargs):
        if 'back' in request.POST:
            return redirect('landing')  # Go back to landing page
        return super().post(request, *args, **kwargs)
            
    def form_invalid(self, form):
        print(f"Form errors: {form.errors}")  # Debug log
        return super().form_invalid(form)

class EnterpriseDetailsView(UpdateView):
    model = Organization
    form_class = EnterpriseDetailsForm
    template_name = 'organizations/registration/enterprise_details.html'
    
    def get_initial(self):
        """Pre-populate form with session data"""
        initial = super().get_initial()
        reg_data = self.request.session.get('registration_data', {})
        
        # Add email from registration data to avoid asking again
        if 'email' in reg_data:
            initial['primary_contact_email'] = reg_data['email']
            
        return initial
    
    def form_valid(self, form):
        try:
            organization = form.save(commit=False)
            
            # Get email from session instead of form
            reg_data = self.request.session.get('registration_data', {})
            organization.primary_contact_email = reg_data.get('email')
            
            organization.save()
            
            # Skip pilot definition step and go directly to registration completion
            view = OrganizationRegistrationView()
            view.request = self.request
            return view.complete_registration(organization)
            
        except Exception as e:
            print(f"Error in enterprise details: {e}")
            messages.error(self.request, "Error updating enterprise details. Please try again.")
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        """Make sure we don't lose the entered values"""
        print(f"Form errors: {form.errors}")  # Debug log
        return super().form_invalid(form)
    
class StartupDirectoryView(LoginRequiredMixin, ListView):
    model = Organization
    template_name = 'organizations/startup_directory.html'
    context_object_name = 'startups'
    
    def get_queryset(self):
        # Show all startups except the current user's organization
        return Organization.objects.filter(
            type='startup',
            onboarding_completed=True
        ).exclude(
            id=self.request.user.organization.id
        ).order_by('name')

class PilotDefinitionView(CreateView):
    model = PilotDefinition
    form_class = PilotDefinitionForm
    template_name = 'organizations/registration/pilot_definition.html'

    def form_valid(self, form):
        try:
            organization = Organization.objects.get(pk=self.kwargs['pk'])
            pilot_definition = form.save(commit=False)
            pilot_definition.organization = organization
            pilot_definition.save()
            
            # Create a draft pilot from this definition
            if form.cleaned_data.get('description'):
                from apps.pilots.models import Pilot
                pilot = Pilot.objects.create(
                    organization=organization,
                    pilot_definition=pilot_definition,
                    title=f"{organization.name} - Initial Pilot",
                    description=form.cleaned_data.get('description'),
                    technical_specs_doc=form.cleaned_data.get('technical_specs_doc'),
                    performance_metrics=form.cleaned_data.get('performance_metrics'),
                    compliance_requirements=form.cleaned_data.get('compliance_requirements'),
                    is_private=form.cleaned_data.get('is_private', False),
                    status='draft',
                    price=0  # Default price, can be updated later
                )
            
            # Complete the registration process
            view = OrganizationRegistrationView()
            view.request = self.request
            return view.complete_registration(organization)
        except Exception as e:
            print(f"Error in pilot definition: {e}")
            messages.error(self.request, "Error creating pilot definition. Please try again.")
            return self.form_invalid(form)

    def post(self, request, *args, **kwargs):
        if 'back' in request.POST:
            return redirect('organizations:enterprise_details', pk=self.kwargs['pk'])
        return super().post(request, *args, **kwargs)

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
        if request.user.organization.type == 'enterprise':
            return redirect('organizations:enterprise_dashboard')
        return redirect('organizations:startup_dashboard')

# class EnterpriseDashboardView(LoginRequiredMixin, TemplateView):
#     template_name = 'organizations/dashboard/enterprise.html'

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context['active_pilots'] = Pilot.objects.filter(
#             organization=self.request.user.organization
#         ).order_by('-created_at')[:5]  # Get 5 most recent pilots
#         return context

class EnterpriseDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'organizations/dashboard/enterprise.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_org = self.request.user.organization
        
        # Get all pilots for this enterprise
        context['active_pilots'] = Pilot.objects.filter(
            organization=user_org
        ).order_by('-created_at')[:5]  # Get 5 most recent pilots
        
        # Get other enterprises for display
        context['enterprises'] = Organization.objects.filter(
            type='enterprise',
            onboarding_completed=True
        ).exclude(
            id=user_org.id
        ).order_by('?')[:4]  # Random selection of 4 other enterprises
        
        # Get startups for display
        context['startups'] = Organization.objects.filter(
            type='startup',
            onboarding_completed=True
        ).order_by('?')[:4]  # Random selection of 4 startups
        
        return context

# class StartupDashboardView(LoginRequiredMixin, TemplateView):
#     template_name = 'organizations/dashboard/startup.html'

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context['available_pilots'] = Pilot.objects.filter(
#             status='published',
#             is_private=False
#         ).order_by('-created_at')[:5]  # Get 5 most recent public pilots
#         return context

class StartupDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'organizations/dashboard/startup.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_org = self.request.user.organization
        
        # Get available pilots for startups
        pilots = Pilot.objects.filter(
            status='published',
            is_private=False
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
            onboarding_completed=True
        ).exclude(
            id=user_org.id
        ).order_by('?')[:4]  # Random selection of 4 other startups
        
        # Get enterprise partners - alphabetical order
        context['enterprises'] = Organization.objects.filter(
            type='enterprise',
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
        # Show all enterprises except the current user's organization
        return Organization.objects.filter(
            type='enterprise',
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
        # Add published pilots for enterprises
        if self.object.type == 'enterprise':
            context['published_pilots'] = self.object.pilots.filter(
                status='published',
                is_private=False
            )
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