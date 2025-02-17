from django.views.generic import CreateView, UpdateView, TemplateView
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from .models import Organization, PilotDefinition
from .forms import OrganizationBasicForm, EnterpriseDetailsForm, PilotDefinitionForm

class OrganizationRegistrationView(CreateView):
    model = Organization
    form_class = OrganizationBasicForm
    template_name = 'organizations/registration/basic.html'
    
    def form_valid(self, form):
        try:
            organization = form.save()
            print(f"Organization created: {organization.pk}, Type: {organization.type}")  # Debug log
            
            if organization.type == 'enterprise':
                return redirect('organizations:enterprise_details', pk=organization.pk)
            
            organization.onboarding_completed = True
            organization.save()
            return redirect('organizations:registration_complete')
            
        except Exception as e:
            print(f"Error in form_valid: {e}")  # Debug log
            messages.error(self.request, "Error creating organization. Please try again.")
            return self.form_invalid(form)
    
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
    
    def form_valid(self, form):
        try:
            organization = form.save()
            print(f"Enterprise details updated for org: {organization.pk}")  # Debug log
            return redirect('organizations:pilot_definition', pk=organization.pk)
        except Exception as e:
            print(f"Error in enterprise details: {e}")  # Debug log
            messages.error(self.request, "Error updating enterprise details. Please try again.")
            return self.form_invalid(form)
    
    def post(self, request, *args, **kwargs):
        if 'back' in request.POST:
            # Delete the incomplete organization
            org = get_object_or_404(Organization, pk=self.kwargs['pk'])
            org.delete()
            return redirect('organizations:register')
        return super().post(request, *args, **kwargs)

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
            
            organization.onboarding_completed = True
            organization.save()
            print(f"Pilot definition created for org: {organization.pk}")  # Debug log
            
            return redirect('organizations:registration_complete')
        except Exception as e:
            print(f"Error in pilot definition: {e}")  # Debug log
            messages.error(self.request, "Error creating pilot definition. Please try again.")
            return self.form_invalid(form)

    def post(self, request, *args, **kwargs):
        if 'back' in request.POST:
            return redirect('organizations:enterprise_details', pk=self.kwargs['pk'])
        return super().post(request, *args, **kwargs)
    
class RegistrationCompleteView(TemplateView):
    template_name = 'organizations/registration/complete.html'