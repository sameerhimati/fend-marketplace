from django.views.generic import CreateView, UpdateView, TemplateView, ListView, DetailView
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.contrib.auth import login as auth_login, get_user_model
from django.db import transaction
from .models import Organization, PilotDefinition
from .forms import OrganizationBasicForm, EnterpriseDetailsForm, PilotDefinitionForm, OrganizationProfileForm
from django.views.generic import TemplateView
from django.contrib.auth.views import LoginView
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.pilots.models import Pilot, PilotBid
from django.utils import timezone
from apps.users.models import User, EmailVerificationToken
from apps.payments.emails import send_verification_email, send_welcome_email
from django.urls import reverse
from django.views import View

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

            self.request.session.modified = True
            
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
                password=reg_data['password'],
                is_verified=False  # Start as unverified
            )
            
            # Link user to organization
            user.organization = organization
            user.save()
            
            # Mark organization as partially complete (waiting for email verification)
            organization.onboarding_completed = False  # Keep as False until email verified
            organization.save()
            
            # Generate verification token
            token = EmailVerificationToken.generate_token(user)
            
            # Build verification URL
            verification_url = self.request.build_absolute_uri(
                reverse('organizations:verify_email', args=[token.token])
            )
            
            # Send verification email
            send_verification_email(user, verification_url)
            
            # Clean up session
            if 'registration_data' in self.request.session:
                del self.request.session['registration_data']
            if 'organization_id' in self.request.session:
                del self.request.session['organization_id']
            
            # DON'T log the user in yet - they need to verify email first
            
            messages.info(self.request, "Registration successful! Please check your email to verify your account.")
            return redirect('organizations:verification_pending')
        
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

class EmailVerificationView(View):
    def get(self, request, token):
        verification_token = get_object_or_404(EmailVerificationToken, token=token)
        
        if verification_token.used:
            messages.error(request, "This verification link has already been used.")
            return redirect('organizations:login')
            
        if verification_token.is_expired():
            messages.error(request, "This verification link has expired. Please request a new one.")
            return redirect('organizations:resend_verification')
            
        # Mark user as verified
        user = verification_token.user
        user.is_verified = True
        user.save()
        
        # Mark token as used
        verification_token.used = True
        verification_token.save()
        
        # Mark organization as complete
        if user.organization:
            user.organization.onboarding_completed = True
            user.organization.save()
        
        # Send welcome email
        send_welcome_email(user)
        
        # Log the user in
        auth_login(request, user)
        
        messages.success(request, "Email verified successfully! Please select a subscription plan to continue.")
        return redirect('payments:payment_selection')

class VerificationPendingView(TemplateView):
    template_name = 'organizations/verification_pending.html'

class ResendVerificationView(View):
    def get(self, request):
        return render(request, 'organizations/resend_verification.html')
    
    def post(self, request):
        email = request.POST.get('email')
        
        try:
            user = User.objects.get(email=email, is_verified=False)
            
            # Generate new token
            token = EmailVerificationToken.generate_token(user)
            
            # Build verification URL
            verification_url = request.build_absolute_uri(
                reverse('organizations:verify_email', args=[token.token])
            )
            
            # Send verification email
            send_verification_email(user, verification_url)
            
            messages.success(request, "Verification email sent! Please check your inbox.")
            return redirect('organizations:verification_pending')
            
        except User.DoesNotExist:
            messages.error(request, "No unverified account found with this email address.")
            return render(request, 'organizations/resend_verification.html')
        

class EnterpriseDetailsView(UpdateView):
    model = Organization
    form_class = EnterpriseDetailsForm
    template_name = 'organizations/registration/enterprise_details.html'
    
    def get_initial(self):
        """Pre-populate form with session data if available"""
        initial = super().get_initial()
        reg_data = self.request.session.get('registration_data', {})
        
        # Get organization data from session if previous form data exists
        org_data = self.request.session.get('enterprise_details', {})
        if org_data:
            initial.update({
                'business_type': org_data.get('business_type', ''),
                'business_registration_number': org_data.get('business_registration_number', ''),
                'primary_contact_name': org_data.get('primary_contact_name', ''),
                'primary_contact_phone': org_data.get('primary_contact_phone', ''),
            })
        
        # Add email from registration data to avoid asking again
        if 'email' in reg_data:
            initial['primary_contact_email'] = reg_data['email']
            
        return initial
    
    def form_valid(self, form):
        try:
            # Store form data in session before saving
            self.request.session['enterprise_details'] = {
                'business_type': form.cleaned_data.get('business_type'),
                'business_registration_number': form.cleaned_data.get('business_registration_number'),
                'primary_contact_name': form.cleaned_data.get('primary_contact_name'),
                'primary_contact_phone': form.cleaned_data.get('primary_contact_phone'),
            }
            self.request.session.modified = True
            
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

@login_required
def update_bank_info(request):
    """Update organization bank information"""
    if request.method != 'POST':
        return redirect('organizations:profile', pk=request.user.organization.id)
    
    organization = request.user.organization
    
    # Update only the fields we need
    organization.bank_name = request.POST.get('bank_name', '')
    organization.bank_account_number = request.POST.get('bank_account_number', '')
    organization.bank_routing_number = request.POST.get('bank_routing_number', '')
    organization.save()
    
    messages.success(request, "Bank information updated successfully")
    return redirect('organizations:profile', pk=organization.id)

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
    
    def form_valid(self, form):
        """Override form_valid to check email verification"""
        user = form.get_user()
        
        if not user.is_verified:
            messages.error(self.request, "Please verify your email address before logging in. Check your inbox for the verification link.")
            return self.form_invalid(form)
        
        return super().form_valid(form)
    
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