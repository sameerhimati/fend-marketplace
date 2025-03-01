from django.views.generic import CreateView, UpdateView, TemplateView
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.contrib.auth import login, get_user_model
from django.db import transaction
from .models import Organization, PilotDefinition
from .forms import OrganizationBasicForm, EnterpriseDetailsForm, PilotDefinitionForm
from django.views.generic import TemplateView
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.pilots.models import Pilot

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
            return redirect('organizations:registration_complete')
        
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
            return redirect('organizations:pilot_definition', pk=organization.pk)
        except Exception as e:
            print(f"Error in enterprise details: {e}")
            messages.error(self.request, "Error updating enterprise details. Please try again.")
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        """Make sure we don't lose the entered values"""
        print(f"Form errors: {form.errors}")  # Debug log
        return super().form_invalid(form)

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



class RegistrationCompleteView(LoginRequiredMixin, TemplateView):
    template_name = 'organizations/registration/complete.html'
    
    def get(self, request, *args, **kwargs):
        # If user has been on this page for more than 3 seconds, redirect to dashboard
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
    template_name = 'pilots/pilot_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get all pilots for this enterprise
        context['pilots'] = Pilot.objects.filter(
            organization=self.request.user.organization
        ).order_by('-created_at')
        context['is_dashboard'] = True  # Flag to indicate this is the dashboard view
        context['dashboard_title'] = "Your Pilots"
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
    template_name = 'pilots/pilot_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get all available pilots for startups
        pilots = Pilot.objects.filter(
            status='published',
            is_private=False
        ).order_by('-created_at')
        
        # Exclude pilots where this startup already has an approved bid
        user_org = self.request.user.organization
        from apps.pilots.models import PilotBid
        
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
        context['is_dashboard'] = True  # Flag to indicate this is the dashboard view
        context['dashboard_title'] = "Available Pilot Opportunities"
        return context
    
class CustomLoginView(LoginView):
    template_name = 'organizations/auth/login.html'
    
    def get_success_url(self):
        return reverse_lazy('organizations:dashboard')