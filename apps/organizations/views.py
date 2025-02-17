from django.views.generic import CreateView, UpdateView, TemplateView
from django.shortcuts import redirect
from .models import Organization, PilotDefinition
from .forms import OrganizationBasicForm, EnterpriseDetailsForm, PilotDefinitionForm

class OrganizationRegistrationView(CreateView):
    model = Organization
    form_class = OrganizationBasicForm
    template_name = 'organizations/registration/basic.html'
    
    def form_valid(self, form):
        organization = form.save()
        if organization.type == 'enterprise':
            return redirect('organizations:enterprise_details', pk=organization.pk)
        organization.onboarding_completed = True
        organization.save()
        return redirect('organizations:registration_complete')

class EnterpriseDetailsView(UpdateView):
    model = Organization
    form_class = EnterpriseDetailsForm
    template_name = 'organizations/registration/enterprise_details.html'
    
    def form_valid(self, form):
        organization = form.save()
        return redirect('organizations:pilot_definition', pk=organization.pk)

class PilotDefinitionView(CreateView):
    model = PilotDefinition
    form_class = PilotDefinitionForm
    template_name = 'organizations/registration/pilot_definition.html'
    
    def form_valid(self, form):
        organization = Organization.objects.get(pk=self.kwargs['pk'])
        pilot_definition = form.save(commit=False)
        pilot_definition.organization = organization
        pilot_definition.save()
        organization.onboarding_completed = True
        organization.save()
        return redirect('organizations:registration_complete')

class RegistrationCompleteView(TemplateView):
    template_name = 'organizations/registration/complete.html'