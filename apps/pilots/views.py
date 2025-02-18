from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse_lazy, reverse
from .models import Pilot, PilotBid
from .forms import PilotBidForm
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

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

@login_required
def publish_pilot(request, pk):
    if request.method != 'POST':
        return redirect('pilots:detail', pk=pk)
        
    pilot = get_object_or_404(Pilot, pk=pk)
    
    # Check permissions
    if request.user.organization != pilot.organization:
        raise PermissionDenied
    
    if pilot.status != 'draft':
        messages.error(request, "Only draft pilots can be published.")
        return redirect('pilots:detail', pk=pk)
    
    # Update status to published
    pilot.status = 'published'
    pilot.save()
    
    messages.success(request, f"'{pilot.title}' has been published successfully!")
    return redirect('pilots:detail', pk=pk)

@login_required
def create_bid(request, pilot_id):
    """Allow startups to submit bids on pilots"""
    pilot = get_object_or_404(Pilot, id=pilot_id, status='published', is_private=False)
    user_org = request.user.organization
    
    # Only startups can create bids
    if user_org.type != 'startup':
        messages.error(request, "Only startups can submit bids")
        return redirect('pilots:detail', pk=pilot_id)
    
    # Check if startup already has a bid for this pilot
    existing_bid = PilotBid.objects.filter(pilot=pilot, startup=user_org).first()
    if existing_bid:
        messages.info(request, "You've already submitted a bid for this pilot")
        return redirect('pilots:bid_detail', pk=existing_bid.pk)
    
    if request.method == 'POST':
        form = PilotBidForm(request.POST)
        if form.is_valid():
            bid = form.save(commit=False)
            bid.pilot = pilot
            bid.startup = user_org
            bid.save()
            messages.success(request, "Your bid has been submitted successfully")
            return redirect('pilots:bid_detail', pk=bid.pk)
    else:
        form = PilotBidForm()
    
    return render(request, 'pilots/bid_form.html', {
        'form': form,
        'pilot': pilot
    })

class BidListView(LoginRequiredMixin, ListView):
    """View for listing bids - for both startups and enterprises"""
    model = PilotBid
    template_name = 'pilots/bid_list.html'
    context_object_name = 'bids'
    
    def get_queryset(self):
        user_org = self.request.user.organization
        if user_org.type == 'startup':
            # Startups see their submitted bids
            return PilotBid.objects.filter(startup=user_org)
        elif user_org.type == 'enterprise':
            # Enterprises see bids received on their pilots
            return PilotBid.objects.filter(pilot__organization=user_org)
        return PilotBid.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_enterprise'] = self.request.user.organization.type == 'enterprise'
        return context

class BidDetailView(LoginRequiredMixin, DetailView):
    """View for both enterprises and startups to see bid details"""
    model = PilotBid
    template_name = 'pilots/bid_detail.html'
    context_object_name = 'bid'
    
    def get_object(self, queryset=None):
        bid = super().get_object(queryset)
        user_org = self.request.user.organization
        
        # Check permissions
        if user_org == bid.startup or user_org == bid.pilot.organization:
            return bid
        
        messages.error(self.request, "You don't have permission to view this bid")
        raise PermissionDenied("You don't have permission to view this bid")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_enterprise'] = self.request.user.organization == self.object.pilot.organization
        return context

class SubmittedBidsListView(LoginRequiredMixin, ListView):
    """View for startups to see their submitted bids"""
    model = PilotBid
    template_name = 'pilots/submitted_bids.html'
    context_object_name = 'bids'
    
    def get_queryset(self):
        if self.request.user.organization.type == 'startup':
            return PilotBid.objects.filter(startup=self.request.user.organization)
        return PilotBid.objects.none()

class ReceivedBidsListView(LoginRequiredMixin, ListView):
    """View for enterprises to see bids received on their pilots"""
    model = PilotBid
    template_name = 'pilots/received_bids.html'
    context_object_name = 'bids'
    
    def get_queryset(self):
        user_org = self.request.user.organization
        if user_org.type == 'enterprise':
            return PilotBid.objects.filter(pilot__organization=user_org)
        return PilotBid.objects.none()

@login_required
def update_bid_status(request, pk):
    """Allow enterprises to update bid status"""
    if request.method != 'POST':
        return redirect('pilots:bid_detail', pk=pk)
    
    bid = get_object_or_404(PilotBid, pk=pk)
    user_org = request.user.organization
    
    # Check if user has permission (enterprise owner of the pilot)
    if user_org != bid.pilot.organization:
        messages.error(request, "You don't have permission to update this bid")
        return redirect('pilots:bid_detail', pk=pk)
    
    new_status = request.POST.get('status')
    valid_statuses = dict(PilotBid.STATUS_CHOICES)
    if new_status in valid_statuses:
        old_status = bid.status
        bid.status = new_status
        bid.save()
        messages.success(request, f"Bid status updated from {valid_statuses[old_status]} to {valid_statuses[new_status]}")
    else:
        messages.error(request, "Invalid status")
    
    return redirect('pilots:bid_detail', pk=pk)