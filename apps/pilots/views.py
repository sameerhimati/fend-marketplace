from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse_lazy
from .models import Pilot

class PilotListView(LoginRequiredMixin, ListView):
    model = Pilot
    template_name = 'pilots/pilot_list.html'
    context_object_name = 'pilots'

    def get_queryset(self):
        user_org = self.request.user.organization
        if user_org.type == 'startup':
            # Startups see all published, non-private pilots
            return Pilot.objects.filter(status='published', is_private=False)
        elif user_org.type == 'enterprise':
            # Enterprises see all their pilots
            return Pilot.objects.filter(organization=user_org)
        return Pilot.objects.none()

class PilotDetailView(LoginRequiredMixin, DetailView):
    model = Pilot
    template_name = 'pilots/pilot_detail.html'
    context_object_name = 'pilot'

    def get_object(self, queryset=None):
        pilot = super().get_object(queryset)
        user_org = self.request.user.organization

        # Check if user has permission to view this pilot
        if user_org.type == 'startup' and (pilot.is_private or pilot.status != 'published'):
            raise PermissionDenied
        elif user_org.type == 'enterprise' and pilot.organization != user_org:
            raise PermissionDenied
        return pilot

class PilotCreateView(LoginRequiredMixin, CreateView):
    model = Pilot
    template_name = 'pilots/pilot_form.html'
    fields = ['title', 'description', 'technical_specs_doc', 'performance_metrics', 
              'compliance_requirements', 'is_private']
    success_url = reverse_lazy('pilots:list')

    def dispatch(self, request, *args, **kwargs):
        # Only enterprise users can create pilots
        if request.user.organization.type != 'enterprise':
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.organization = self.request.user.organization
        form.instance.status = 'draft'  # Default to draft status
        return super().form_valid(form)