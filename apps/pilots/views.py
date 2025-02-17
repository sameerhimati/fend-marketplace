from django.views.generic import ListView, DetailView
from .models import Pilot

class PilotListView(ListView):
    model = Pilot
    template_name = 'pilots/pilot_list.html'
    context_object_name = 'pilots'

    def get_queryset(self):
        # Everyone can see published pilots
        return Pilot.objects.filter(status='published')

class PilotDetailView(DetailView):
    model = Pilot
    template_name = 'pilots/pilot_detail.html'
    context_object_name = 'pilot'