from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse_lazy, reverse
from .models import Pilot, PilotBid
from .forms import PilotBidForm
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from apps.notifications.services import create_bid_notification, create_pilot_notification, create_notification
from django.contrib.auth import get_user_model

from datetime import timezone

class PilotListView(LoginRequiredMixin, ListView):
    model = Pilot
    template_name = 'pilots/pilot_list.html'
    context_object_name = 'pilots'

    def get_queryset(self):
        user_org = self.request.user.organization
        if user_org.type == 'startup':
            # Get all published, non-private pilots
            pilots = Pilot.objects.filter(status='published', is_private=False)
            
            # Exclude pilots where this startup already has an approved, pending or under_review bid
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
            
            # Exclude those pilots
            return pilots.exclude(id__in=excluded_pilots)
            
        elif user_org.type == 'enterprise':
            # Enterprises see all their pilots
            return Pilot.objects.filter(organization=user_org)
        return Pilot.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add enterprise partners for showcase when no pilots are available
        if self.request.user.organization.type == 'startup' and not context['pilots']:
            # Get a few featured enterprise partners (limit to 6 for display)
            from apps.organizations.models import Organization
            enterprises = Organization.objects.filter(
                type='enterprise',
                onboarding_completed=True
            ).order_by('?')[:6]  # Random selection, limited to 6
            
            context['enterprises'] = enterprises
            
        return context

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_org = self.request.user.organization
        pilot = self.object
        
        # Check if this startup had a declined bid for this pilot
        if user_org.type == 'startup':
            declined_bid = PilotBid.objects.filter(
                pilot=pilot,
                startup=user_org,
                status='declined'
            ).first()
            
            if declined_bid:
                context['previous_bid_declined'] = True
                context['declined_bid'] = declined_bid
        
        # Add pilot-specific context here
        context['is_enterprise'] = user_org == pilot.organization
        context['can_edit'] = pilot.can_be_edited_by(self.request.user) if hasattr(pilot, 'can_be_edited_by') else False
        
        return context

class PilotCreateView(LoginRequiredMixin, CreateView):
    model = Pilot
    template_name = 'pilots/pilot_form.html'
    fields = ['title', 'description', 'technical_specs_doc', 'performance_metrics', 
              'compliance_requirements', 'is_private', 'price']
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

class PilotUpdateView(LoginRequiredMixin, UpdateView):
    model = Pilot
    template_name = 'pilots/pilot_form.html'
    fields = ['title', 'description', 'technical_specs_doc', 'performance_metrics', 
              'compliance_requirements', 'is_private', 'price']
    context_object_name = 'pilot'
    
    def dispatch(self, request, *args, **kwargs):
        pilot = self.get_object()
        if not pilot.can_be_edited_by(request.user):
            messages.error(request, "You don't have permission to edit this pilot")
            return redirect('pilots:detail', pk=pilot.pk)
        return super().dispatch(request, *args, **kwargs)
    
    def get_success_url(self):
        return reverse_lazy('pilots:detail', kwargs={'pk': self.object.pk})
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_edit'] = True  # Add this to indicate we're editing
        return context

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
    
    # Check subscription status
    organization = request.user.organization
    if not organization.has_active_subscription():
        messages.error(request, "You need an active subscription to access pilot publishing features. Please complete the payment process.")
        return redirect('payments:subscription_detail')
    
    # Check token availability
    if not organization.has_available_tokens():
        messages.error(request, "You don't have any tokens available. Please purchase tokens to publish this pilot.")
        return redirect('payments:token_packages')
        
    try:
        # Update status to published
        pilot.status = 'published'
        pilot.save()
        
        # Create notification for pilot publication
        create_pilot_notification(
            pilot=pilot,
            notification_type='pilot_updated',
            title=f"Pilot published: {pilot.title}",
            message=f"Your pilot '{pilot.title}' has been published successfully and is now visible to startups. A token has been consumed."
        )
        
        messages.success(request, f"'{pilot.title}' has been published successfully! One token has been consumed.")
        
    except ValidationError as e:
        messages.error(request, str(e))
        
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
    
    # Check if startup already has an active bid for this pilot
    existing_bid = PilotBid.objects.filter(
        pilot=pilot, 
        startup=user_org
    ).exclude(
        status='declined'  # Allow resubmission if previous bid was declined
    ).first()
    
    if existing_bid:
        messages.info(request, "You already have an active bid for this pilot")
        return redirect('pilots:bid_detail', pk=existing_bid.pk)
    
    if request.method == 'POST':
        form = PilotBidForm(request.POST, initial={'pilot': pilot})
        if form.is_valid():
            bid_amount = form.cleaned_data['amount']
            
            # Validate bid amount against pilot price
            if bid_amount < pilot.price:
                messages.error(request, f"Bid amount must be at least ${pilot.price}")
                return render(request, 'pilots/bid_form.html', {'form': form, 'pilot': pilot})
            
            bid = form.save(commit=False)
            bid.pilot = pilot
            bid.startup = user_org
            bid.save()
            
            create_bid_notification(
                bid=bid,
                notification_type='bid_submitted',
                title=f"New bid received: {pilot.title}",
                message=f"{user_org.name} has submitted a new bid of ${bid.amount} for your pilot '{pilot.title}'."
            )

            messages.success(request, "Your bid has been submitted successfully")

            return redirect('pilots:bid_detail', pk=bid.pk)
    else:
        form = PilotBidForm(initial={'pilot': pilot, 'amount': pilot.price})
    
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
        user_org = self.request.user.organization
        
        if user_org.type == 'startup':
            # Separate approved and other bids
            all_bids = PilotBid.objects.filter(startup=user_org)
            context['approved_bids'] = all_bids.filter(status='approved')
            context['other_bids'] = all_bids.exclude(status='approved')
        else:
            # For enterprises, group by pilot
            all_bids = PilotBid.objects.filter(pilot__organization=user_org)
            context['grouped_bids'] = {}
            
            for bid in all_bids:
                if bid.pilot_id not in context['grouped_bids']:
                    context['grouped_bids'][bid.pilot_id] = {
                        'pilot': bid.pilot,
                        'approved_bids': [],
                        'other_bids': []
                    }
                
                if bid.status == 'approved':
                    context['grouped_bids'][bid.pilot_id]['approved_bids'].append(bid)
                else:
                    context['grouped_bids'][bid.pilot_id]['other_bids'].append(bid)
        
        context['is_enterprise'] = user_org.type == 'enterprise'
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
        user_org = self.request.user.organization
        bid = self.object
        
        # Determine if the current user can delete the bid
        can_delete = False
        
        # Startup can delete their own bids if they're still pending
        if user_org == bid.startup and bid.status == 'pending':
            can_delete = True
        
        # Enterprise can delete/reject any pending bid on their pilot
        elif user_org == bid.pilot.organization and bid.status == 'pending':
            can_delete = True
        
        context['is_enterprise'] = user_org == bid.pilot.organization
        context['can_delete_bid'] = can_delete
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
        
        # Create notification for bid status update
        create_bid_notification(
            bid=bid,
            notification_type='bid_updated',
            title=f"Bid status updated: {bid.pilot.title}",
            message=f"The status of your bid for '{bid.pilot.title}' has been updated from '{valid_statuses[old_status]}' to '{valid_statuses[new_status]}'."
        )
        
        messages.success(request, f"Bid status updated from {valid_statuses[old_status]} to {valid_statuses[new_status]}")
    else:
        messages.error(request, "Invalid status")
    
    return redirect('pilots:bid_detail', pk=pk)


@login_required
def delete_bid(request, pk):
    """Allow users to delete bids based on permissions"""
    if request.method != 'POST':
        return redirect('pilots:bid_detail', pk=pk)
    
    bid = get_object_or_404(PilotBid, pk=pk)
    user_org = request.user.organization
    
    # Determine who can delete the bid
    can_delete = False
    delete_reason = None
    
    # Startup can delete their own bids if they're still in pending status
    if user_org == bid.startup and bid.status == 'pending':
        can_delete = True
        delete_reason = "withdrawn by startup"
    
    # Enterprise can delete/reject any pending bid on their pilot
    elif user_org == bid.pilot.organization and bid.status == 'pending':
        can_delete = True
        delete_reason = "rejected by enterprise"
    
    if not can_delete:
        messages.error(request, "You don't have permission to delete this bid")
        return redirect('pilots:bid_detail', pk=pk)
    
    # Create notification before deleting
    from apps.notifications.services import create_bid_notification
    create_bid_notification(
        bid=bid,
        notification_type='bid_updated',
        title=f"Bid {delete_reason}: {bid.pilot.title}",
        message=f"A bid of ${bid.amount} for pilot '{bid.pilot.title}' has been {delete_reason}."
    )
    
    # Delete the bid
    bid.delete()
    
    messages.success(request, f"Bid has been successfully {delete_reason}.")
    
    # Redirect to appropriate page based on user type
    if user_org.type == 'startup':
        return redirect('pilots:bid_list')
    else:
        return redirect('pilots:list')
    

@login_required
def delete_pilot(request, pk):
    """Delete a pilot"""
    if request.method != 'POST':
        return redirect('pilots:detail', pk=pk)
        
    pilot = get_object_or_404(Pilot, pk=pk)
    
    # Check permissions
    if request.user.organization != pilot.organization:
        messages.error(request, "You don't have permission to delete this pilot")
        raise PermissionDenied
    
    # Create notification for pilot deletion
    create_pilot_notification(
        pilot=pilot,
        notification_type='pilot_updated',
        title=f"Pilot deleted: {pilot.title}",
        message=f"The pilot '{pilot.title}' has been deleted."
    )
    
    # Delete the pilot
    pilot.delete()
    messages.success(request, "Pilot deleted successfully")
    
    return redirect('pilots:list')


@login_required
def finalize_pilot(request, pk):
    """Mark a pilot as completed and trigger payment release workflow"""
    if request.method != 'POST':
        return redirect('pilots:bid_detail', pk=pk)
    
    bid = get_object_or_404(PilotBid, pk=pk)
    user_org = request.user.organization
    
    # Check if user has permission (enterprise owner of the pilot)
    if user_org != bid.pilot.organization:
        messages.error(request, "You don't have permission to finalize this pilot")
        return redirect('pilots:bid_detail', pk=pk)
    
    # Check if escrow payment exists and has been received
    if not hasattr(bid, 'escrow_payment') or bid.escrow_payment.status != 'received':
        messages.error(request, "Payment must be received before the pilot can be marked as completed")
        return redirect('pilots:bid_detail', pk=pk)
    
    # Update bid status
    bid.status = 'completed'
    bid.completed_at = timezone.now()
    bid.save()

    User = get_user_model()
    
    # Get admin users
    admins = User.objects.filter(is_staff=True)
    for admin in admins:
        create_notification(
            recipient=admin,
            notification_type='pilot_completed',
            title=f"Pilot Completed: {bid.pilot.title}",
            message=f"The pilot '{bid.pilot.title}' has been marked as completed. The payment is ready to be released to the startup.",
            related_pilot=bid.pilot,
            related_bid=bid
        )
    
    # Notify both parties
    create_bid_notification(
        bid=bid,
        notification_type='pilot_completed',
        title=f"Pilot Completed: {bid.pilot.title}",
        message=f"The pilot '{bid.pilot.title}' has been marked as completed. The payment will be released to the startup soon."
    )
    
    messages.success(request, "Pilot has been marked as completed. The payment will be released to the startup by the Fend team.")
    return redirect('pilots:bid_detail', pk=pk)