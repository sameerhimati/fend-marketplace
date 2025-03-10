from django.views.generic import TemplateView
from apps.pilots.models import Pilot
from apps.organizations.models import Organization

class LandingPageView(TemplateView):
    template_name = 'landing.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get featured pilots (published and not private)
        featured_pilots = Pilot.objects.filter(
            status='published',
            is_private=False
        ).order_by('-created_at')[:3]  # Show 3 most recent pilots
        
        # Get featured enterprise partners
        featured_enterprises = Organization.objects.filter(
            type='enterprise',
            onboarding_completed=True
        ).order_by('?')[:5]  # Random selection, limited to 5
        
        context['featured_pilots'] = featured_pilots
        context['featured_enterprises'] = featured_enterprises
        
        return context