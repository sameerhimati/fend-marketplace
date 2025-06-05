from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse_lazy, reverse
from .models import Pilot, PilotBid
from .forms import PilotForm, PilotBidForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseForbidden, JsonResponse
from apps.notifications.services import create_bid_notification, create_pilot_notification, create_notification
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Count, Prefetch
from django.core.paginator import Paginator
from apps.organizations.mixins import OrganizationRequiredMixin

class UnifiedPilotListView(OrganizationRequiredMixin, LoginRequiredMixin, ListView):
    """
    Unified pilot list that shows different content based on user's relationship to each pilot.
    Replaces both PilotListView and BidListView.
    """
    model = Pilot
    template_name = 'pilots/unified_pilot_list.html'
    context_object_name = 'pilot_data'
    paginate_by = 20

    def get_queryset(self):
        if not hasattr(self.request.user, 'organization') or self.request.user.organization is None:
            return Pilot.objects.none()
            
        user_org = self.request.user.organization
        
        if user_org.type == 'enterprise':
            # Enterprises see all their pilots
            pilots = Pilot.objects.filter(
                organization=user_org
            ).prefetch_related(
                'bids__startup',
                'organization'
            ).order_by('-created_at')
            
        elif user_org.type == 'startup':
            # Startups see:
            # 1. Available pilots they can bid on
            # 2. Pilots they have bids on (any status)
            
            # Available pilots (published, not private, no approved bids, they haven't bid)
            available_pilots = Pilot.objects.filter(
                status='published',
                is_private=False,
                organization__approval_status='approved'
            ).exclude(
                # Exclude pilots with approved bids
                bids__status__in=['approved', 'live', 'completion_pending', 'completed']
            ).exclude(
                # Exclude pilots they've already bid on
                bids__startup=user_org
            )
            
            # Pilots they have bids on
            bid_pilot_ids = PilotBid.objects.filter(
                startup=user_org
            ).values_list('pilot_id', flat=True)
            
            bid_pilots = Pilot.objects.filter(
                id__in=bid_pilot_ids
            ).prefetch_related(
                'bids__startup',
                'organization'
            )
            
            # Combine and order by relevance
            pilots = available_pilots.union(bid_pilots).order_by('-created_at')
            
        else:
            return Pilot.objects.none()
            
        return pilots

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_org = self.request.user.organization
        
        # Enhance each pilot with relationship data
        pilot_data = []
        for pilot in context['object_list']:
            relationship = pilot.get_user_relationship(self.request.user)
            pilot_data.append({
                'pilot': pilot,
                'relationship': relationship,
                'summary': pilot.get_display_summary(self.request.user),
                'next_action': pilot.get_next_action(self.request.user),
            })
        
        context['pilot_data'] = pilot_data
        context['is_enterprise'] = user_org.type == 'enterprise'
        context['is_startup'] = user_org.type == 'startup'
        context['user_org'] = user_org
        
        # Add counts for enterprise dashboard
        if user_org.type == 'enterprise':
            context['pilot_counts'] = {
                'total': len([p for p in pilot_data if p['relationship']['type'] == 'owner']),
                'active_work': len([p for p in pilot_data if p['relationship'].get('has_approved_bid', False)]),
                'pending_bids': len([p for p in pilot_data if p['relationship'].get('pending_bids_count', 0) > 0]),
                'available': len([p for p in pilot_data if p['relationship'].get('bids_count', 0) == 0]),
            }
        
        # Add counts for startup dashboard  
        if user_org.type == 'startup':
            context['pilot_counts'] = {
                'available': len([p for p in pilot_data if p['relationship']['type'] == 'available']),
                'your_bids': len([p for p in pilot_data if p['relationship']['type'] == 'bidder']),
                'active_work': len([p for p in pilot_data if p['relationship'].get('bid_status') in ['approved', 'live', 'completion_pending', 'completed']]),
            }
        
        return context

class StatusAwarePilotDetailView(LoginRequiredMixin, DetailView):
    """
    Pilot detail view that adapts content based on pilot status and user relationship.
    Shows different sections (pilot info, bids, working agreement) based on context.
    """
    model = Pilot
    template_name = 'pilots/pilot_detail.html'
    context_object_name = 'pilot'

    def get_object(self, queryset=None):
        pilot = super().get_object(queryset)
        user_org = self.request.user.organization
        
        # Basic permission check - allow if user has any valid relationship
        relationship = pilot.get_user_relationship(self.request.user)
        if relationship['type'] == 'none':
            raise PermissionDenied("You don't have permission to view this pilot")
        
        return pilot

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pilot = self.object
        
        # Get user relationship data
        relationship = pilot.get_user_relationship(self.request.user)
        context['relationship'] = relationship
        context['summary'] = pilot.get_display_summary(self.request.user)
        context['next_action'] = pilot.get_next_action(self.request.user)
        
        # Add role flags for template logic
        context['is_owner'] = relationship['type'] == 'owner'
        context['is_bidder'] = relationship['type'] == 'bidder'
        context['can_bid'] = relationship.get('can_bid', False)
        context['has_working_agreement'] = 'working_agreement' in relationship
        
        # Add specific action permissions
        context['can_edit'] = relationship.get('can_edit', False)
        context['can_delete'] = relationship.get('can_delete', False)
        context['can_withdraw_bid'] = relationship.get('can_withdraw', False)
        
        # Set completion permissions based on the active bid
        active_bid = None
        if relationship.get('active_bid'):
            active_bid = relationship['active_bid']
        elif relationship.get('bid') and relationship['bid'].is_active():
            active_bid = relationship['bid']
        
        if active_bid:
            context['can_request_completion'] = (
                relationship['type'] == 'bidder' and 
                active_bid.can_request_completion()
            )
            context['can_verify_completion'] = (
                relationship['type'] == 'owner' and 
                active_bid.can_verify_completion()
            )
        else:
            context['can_request_completion'] = False
            context['can_verify_completion'] = False
        
        # For owners, add bid management context
        if relationship['type'] == 'owner' and relationship.get('bids'):
            context['pending_bids'] = relationship['bids'].filter(status__in=['pending', 'under_review'])
            context['approved_bids'] = relationship['bids'].filter(status__in=['approved', 'live', 'completion_pending', 'completed'])
            context['declined_bids'] = relationship['bids'].filter(status='declined')
        
        # For working agreements, add completion context
        if context['has_working_agreement']:
            working_agreement = relationship['working_agreement']
            context['working_agreement'] = working_agreement
        
        return context

# =============================================================================
# LEGACY COMPATIBILITY VIEWS
# =============================================================================

# Keep old view names for URL compatibility
PilotListView = UnifiedPilotListView
PilotDetailView = StatusAwarePilotDetailView

class BidListView(LoginRequiredMixin, ListView):
    """Legacy view - redirects to unified pilots list"""
    def get(self, request, *args, **kwargs):
        messages.info(request, "Bid management has been integrated into the Pilots page.")
        return redirect('pilots:list')

class BidDetailView(LoginRequiredMixin, DetailView):
    """
    Enhanced bid detail that integrates better with unified experience.
    Still needed for direct bid links but integrates better.
    """
    model = PilotBid
    template_name = 'pilots/bid_detail.html'
    context_object_name = 'bid'
    
    def get_object(self, queryset=None):
        bid = super().get_object(queryset)
        
        # Allow admin/staff users to view any bid
        if self.request.user.is_staff or self.request.user.is_superuser:
            return bid
        
        # For regular users, check organization permissions
        user_org = getattr(self.request.user, 'organization', None)
        
        if not user_org:
            messages.error(self.request, "You need to be part of an organization to view bids")
            raise PermissionDenied("Access denied")
        
        # Permission check - only relevant parties can view
        if user_org not in [bid.startup, bid.pilot.organization]:
            messages.error(self.request, "You don't have permission to view this bid")
            raise PermissionDenied("Access denied")
        
        return bid

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bid = self.object
        pilot = bid.pilot
        
        # Add pilot relationship context
        relationship = pilot.get_user_relationship(self.request.user)
        context['pilot_relationship'] = relationship
        context['pilot'] = pilot
        
        # Determine user role
        if self.request.user.is_staff or self.request.user.is_superuser:
            context['is_admin'] = True
            context['is_enterprise'] = False
            context['is_startup'] = False
        else:
            user_org = self.request.user.organization
            context['is_admin'] = False
            context['is_enterprise'] = user_org == bid.pilot.organization
            context['is_startup'] = user_org == bid.startup
        
        # Add action permissions
        context['can_approve'] = (
            context['is_enterprise'] and 
            bid.can_be_approved()
        )
        context['can_withdraw'] = (
            context['is_startup'] and 
            bid.status == 'pending'
        )
        context['can_request_completion'] = (
            context['is_startup'] and 
            bid.can_request_completion()
        )
        context['can_verify_completion'] = (
            context['is_enterprise'] and 
            bid.can_verify_completion()
        )
        
        # Payment information if escrow exists
        if hasattr(bid, 'escrow_payment'):
            context['escrow_payment'] = bid.escrow_payment
        
        # Calculate financial breakdown
        context['financial_breakdown'] = {
            'bid_amount': bid.amount,
            'enterprise_fee': bid.amount * (bid.enterprise_fee_percentage / 100),
            'total_enterprise_pays': bid.calculate_total_amount_for_enterprise(),
            'startup_fee': bid.amount * (bid.startup_fee_percentage / 100),
            'startup_receives': bid.calculate_startup_net_amount(),
            'platform_total_fee': bid.amount * (bid.fee_percentage / 100)
        }
        
        return context

# =============================================================================
# PILOT MANAGEMENT VIEWS (unchanged)
# =============================================================================

class PilotCreateView(LoginRequiredMixin, CreateView):
    model = Pilot
    form_class = PilotForm
    template_name = 'pilots/pilot_form.html'
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
    form_class = PilotForm
    template_name = 'pilots/pilot_form.html'
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

# =============================================================================
# BID MANAGEMENT FUNCTIONS
# =============================================================================
@login_required
def update_bid_status(request, pk):
    """Enhanced bid status updates with rejection comments"""
    if request.method != 'POST':
        return redirect('pilots:detail', pk=pk)
    
    bid = get_object_or_404(PilotBid, pk=pk)
    user_org = request.user.organization
    
    # Check permissions - only enterprise can update bid status
    if user_org != bid.pilot.organization:
        messages.error(request, "You don't have permission to update this bid")
        return redirect('pilots:detail', pk=bid.pilot.pk)
    
    action = request.POST.get('action')
    
    if action == 'approve':
        success = bid.approve_bid()
        if success:
            messages.success(request, f"Bid approved! An invoice will be sent and you'll be notified when payment is verified.")
        else:
            messages.error(request, "Unable to approve bid at this time.")
    
    elif action == 'decline':
        # Get rejection reason
        rejection_reason = request.POST.get('rejection_reason', '').strip()
        if not rejection_reason:
            messages.error(request, "Please provide a reason for declining this bid.")
            return redirect('pilots:detail', pk=bid.pilot.pk)
        
        success = bid.decline_bid_with_reason(declined_by_enterprise=True, reason=rejection_reason)
        if success:
            messages.success(request, "Bid has been declined with feedback sent to the startup.")
        else:
            messages.error(request, "Unable to decline bid at this time.")
    
    elif action == 'review':
        if bid.status == 'pending':
            bid.status = 'under_review'
            bid.save(update_fields=['status', 'updated_at'])
            
            # Create notification
            create_bid_notification(
                bid=bid,
                notification_type='bid_under_review',
                title=f"Bid under review: {bid.pilot.title}",
                message=f"Your bid for '{bid.pilot.title}' is now under review by {bid.pilot.organization.name}."
            )
            
            messages.success(request, "Bid marked as under review.")
        else:
            messages.error(request, "Bid is not in pending status.")
    
    else:
        messages.error(request, "Invalid action.")
    
    return redirect('pilots:detail', pk=bid.pilot.pk)

@login_required
def create_bid(request, pilot_id):
    """Enhanced bid creation with better validation and resubmission handling"""
    pilot = get_object_or_404(Pilot, id=pilot_id, status='published', is_private=False)
    user_org = request.user.organization
    
    # Only startups can create bids
    if user_org.type != 'startup':
        messages.error(request, "Only startups can submit bids")
        return redirect('pilots:detail', pk=pilot_id)
    
    # Check if startup already has ANY bid for this pilot
    existing_bid = PilotBid.objects.filter(
        pilot=pilot, 
        startup=user_org
    ).first()
    
    # Allow resubmission for declined bids
    is_resubmission = existing_bid and existing_bid.status == 'declined'
    can_edit = existing_bid and existing_bid.status == 'pending'
    
    if existing_bid and not is_resubmission and not can_edit:
        if existing_bid.status in ['under_review', 'approved', 'live', 'completion_pending', 'completed']:
            messages.info(request, "You already have an active bid for this pilot")
            return redirect('pilots:bid_detail', pk=existing_bid.pk)
    
    if request.method == 'POST':
        # Use existing bid instance for resubmission or editing
        form = PilotBidForm(request.POST, instance=existing_bid if (is_resubmission or can_edit) else None)
        if form.is_valid():
            bid_amount = form.cleaned_data['amount']
            
            # Enhanced validation
            if bid_amount <= 0:
                messages.error(request, "Bid amount must be greater than zero")
                return render(request, 'pilots/bid_form.html', {
                    'form': form,
                    'pilot': pilot,
                    'is_resubmission': is_resubmission,
                    'is_edit': can_edit
                })
            
            bid = form.save(commit=False)
            bid.pilot = pilot
            bid.startup = user_org
            bid.startup_fee_percentage = 5.00
            bid.enterprise_fee_percentage = 5.00 
            bid.fee_percentage = 10.00
            
            # Reset status for resubmissions and edits
            if is_resubmission or can_edit:
                bid.status = 'pending'
                
            bid.save()
            
            # Enhanced notification
            action_text = 'revised' if (is_resubmission or can_edit) else 'new'
            create_bid_notification(
                bid=bid,
                notification_type='bid_submitted',
                title=f"{'Revised' if (is_resubmission or can_edit) else 'New'} bid received: {pilot.title}",
                message=f"{user_org.name} has submitted a {action_text} bid of ${bid.amount} for your pilot '{pilot.title}'."
            )

            action_past = 'updated' if can_edit else ('resubmitted' if is_resubmission else 'submitted')
            messages.success(request, f"Your bid has been {action_past} successfully")
            return redirect('pilots:detail', pk=pilot.pk)
    else:
        # For GET requests, pre-populate with existing bid data if available
        initial_data = {}
        if existing_bid and (is_resubmission or can_edit):
            initial_data = {
                'amount': existing_bid.amount,
                'proposal': existing_bid.proposal
            }
        else:
            initial_data = {
                'amount': pilot.price,
                'proposal': ''
            }
        
        form = PilotBidForm(
            initial=initial_data, 
            instance=existing_bid if (is_resubmission or can_edit) else None
        )
    
    return render(request, 'pilots/bid_form.html', {
        'form': form,
        'pilot': pilot,
        'is_resubmission': is_resubmission,
        'is_edit': can_edit,
        'existing_bid': existing_bid
    })

@login_required
def delete_bid(request, pk):
    """Allow startup to withdraw their pending bid"""
    if request.method != 'POST':
        return redirect('pilots:bid_detail', pk=pk)
    
    bid = get_object_or_404(PilotBid, pk=pk)
    user_org = request.user.organization
    pilot_pk = bid.pilot.pk
    
    # Check permissions - only startup can withdraw their own bid
    if user_org != bid.startup:
        messages.error(request, "You don't have permission to withdraw this bid")
        return redirect('pilots:detail', pk=pilot_pk)
    
    # Only allow withdrawal of pending bids
    if bid.status != 'pending':
        messages.error(request, "Only pending bids can be withdrawn")
        return redirect('pilots:detail', pk=pilot_pk)
    
    # Create notification before deleting
    create_pilot_notification(
        pilot=bid.pilot,
        notification_type='bid_withdrawn',
        title=f"Bid Withdrawn: {bid.pilot.title}",
        message=f"{bid.startup.name} has withdrawn their bid of ${bid.amount} for '{bid.pilot.title}'."
    )
    
    # Delete the bid
    bid.delete()
    messages.success(request, "Your bid has been withdrawn successfully.")
    
    return redirect('pilots:detail', pk=pilot_pk)

@login_required
def request_completion(request, bid_id):
    """Enhanced startup completion request"""
    if request.method != 'POST':
        return redirect('pilots:bid_detail', pk=bid_id)
    
    bid = get_object_or_404(PilotBid, pk=bid_id)
    user_org = request.user.organization
    
    # Check permissions - only startup can request completion
    if user_org != bid.startup:
        messages.error(request, "You don't have permission to request completion")
        return redirect('pilots:detail', pk=bid.pilot.pk)
    
    success = bid.request_completion()
    
    if success:
        messages.success(request, "Completion verification requested. The enterprise will review your work.")
    else:
        messages.error(request, "Unable to request completion at this time.")
    
    return redirect('pilots:detail', pk=bid.pilot.pk)

@login_required
def verify_completion(request, bid_id):
    """Enhanced enterprise completion verification"""
    if request.method != 'POST':
        return redirect('pilots:bid_detail', pk=bid_id)
    
    bid = get_object_or_404(PilotBid, pk=bid_id)
    user_org = request.user.organization
    
    # Check permissions - only enterprise can verify completion
    if user_org != bid.pilot.organization:
        messages.error(request, "You don't have permission to verify completion")
        return redirect('pilots:detail', pk=bid.pilot.pk)
    
    success = bid.verify_completion()
    
    if success:
        messages.success(request, "Work completion verified! Payment will be released to the startup by the Fend team.")
    else:
        messages.error(request, "Unable to verify completion at this time.")
    
    return redirect('pilots:detail', pk=bid.pilot.pk)

# =============================================================================
# PILOT ACTION FUNCTIONS
# =============================================================================

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
    
    # Validate legal agreement acceptance
    legal_agreement_accepted = request.POST.get('legal_agreement_accepted') == 'on'
    if not legal_agreement_accepted:
        messages.error(request, "You must accept the legal agreement to publish this pilot.")
        return redirect('pilots:detail', pk=pk)
    
    # Enhanced validation for required fields
    missing_fields = []
    
    # Check technical specs (must have either file or text)
    if not pilot.technical_specs_doc and not pilot.technical_specs_text:
        missing_fields.append("Technical Specifications")
    
    # Check performance metrics (must have either file or text)
    if not pilot.performance_metrics_doc and not pilot.performance_metrics:
        missing_fields.append("Performance Metrics")
    
    # Check compliance requirements (must have either file or text)
    if not pilot.compliance_requirements_doc and not pilot.compliance_requirements:
        missing_fields.append("Compliance Requirements")
    
    # Check if price is set and greater than 0
    if not pilot.price or pilot.price <= 0:
        missing_fields.append("Price (must be greater than 0)")
    
    # If there are missing fields, show error and redirect back
    if missing_fields:
        error_message = f"Cannot publish pilot. Missing required fields: {', '.join(missing_fields)}"
        messages.error(request, error_message)
        return redirect('pilots:detail', pk=pk)
    
    # Check subscription status
    organization = request.user.organization
    if not organization.has_active_subscription():
        messages.error(request, "You need an active subscription to access pilot publishing features. Please complete the payment process.")
        return redirect('payments:subscription_detail')
    
    # Check Pilot availability
    if not organization.get_remaining_pilots():
        messages.error(request, "You don't have any Pilot opportunities available. Please upgrade your plan to publish this pilot.")
        return redirect('payments:subscription_detail')
        
    try:
        # Update status to pending_approval instead of published
        pilot.status = 'pending_approval'
        pilot.legal_agreement_accepted = True
        pilot.save()
        
        # Create notification for pilot submission
        create_pilot_notification(
            pilot=pilot,
            notification_type='pilot_pending_approval',
            title=f"Pilot pending approval: {pilot.title}",
            message=f"Your pilot '{pilot.title}' has been submitted for approval. You will be notified when it is approved or if additional information is needed."
        )
        
        # Create notification for admins
        User = get_user_model()
        admins = User.objects.filter(is_staff=True)
        for admin in admins:
            create_notification(
                recipient=admin,
                notification_type='admin_pilot_verification',
                title=f"New pilot needs verification: {pilot.title}",
                message=f"A new pilot '{pilot.title}' by {pilot.organization.name} needs verification.",
                related_pilot=pilot
            )
        
        messages.success(request, f"'{pilot.title}' has been submitted for approval. You will be notified when it is approved.")
        
    except ValidationError as e:
        messages.error(request, str(e))
        
    return redirect('pilots:detail', pk=pk)

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

# =============================================================================
# ADMIN VIEWS - Pilot Approval Workflow (unchanged from original)
# =============================================================================

@login_required
@staff_member_required
def admin_verify_pilots(request):
    """Enhanced admin view for pilot verification dashboard"""
    # Get all pilots pending approval with optimized queries
    pending_pilots = Pilot.objects.filter(
        status='pending_approval', 
        verified=False
    ).select_related(
        'organization'
    ).prefetch_related(
        'organization__users'
    ).order_by('-updated_at')
    
    # Get stats for the dashboard
    verified_today = Pilot.objects.filter(
        verified=True, 
        admin_verified_at__date=timezone.now().date()
    ).count()
    
    total_verified = Pilot.objects.filter(verified=True).count()
    
    # Handle bulk actions
    if request.method == 'POST':
        action = request.POST.get('action')
        pilot_ids = request.POST.getlist('pilot_ids')
        
        if action == 'bulk_approve' and pilot_ids:
            pilots = Pilot.objects.filter(id__in=pilot_ids, status='pending_approval')
            for pilot in pilots:
                _approve_pilot(request, pilot)
            messages.success(request, f"{len(pilot_ids)} pilots approved successfully.")
        
        # Refresh queryset after actions
        pending_pilots = Pilot.objects.filter(
            status='pending_approval', 
            verified=False
        ).select_related('organization').order_by('-updated_at')
    
    context = {
        'title': 'Pilot Verification',
        'pending_pilots': pending_pilots,
        'verified_today': verified_today,
        'total_verified': total_verified,
    }
    return render(request, 'admin/pilots/pilot/verify.html', context)

@login_required
@staff_member_required
def admin_verify_pilot_detail(request, pk):
    """Enhanced admin view for individual pilot verification"""
    pilot = get_object_or_404(
        Pilot.objects.select_related('organization'),
        pk=pk
    )
    
    # Calculate completion percentage
    requirements_met = 0
    total_requirements = 5
    
    if pilot.technical_specs_doc or pilot.technical_specs_text:
        requirements_met += 1
    if pilot.performance_metrics or pilot.performance_metrics_doc:
        requirements_met += 1
    if pilot.compliance_requirements or pilot.compliance_requirements_doc:
        requirements_met += 1
    if pilot.legal_agreement_accepted:
        requirements_met += 1
    if pilot.price and pilot.price > 0:
        requirements_met += 1
    
    completion_percentage = (requirements_met / total_requirements) * 100
    
    context = {
        'title': f'Verify Pilot: {pilot.title}',
        'pilot': pilot,
        'requirements_met': requirements_met,
        'total_requirements': total_requirements,
        'completion_percentage': completion_percentage,
    }
    return render(request, 'admin/pilots/pilot/verify_detail.html', context)

@login_required
@staff_member_required
def admin_approve_pilot(request, pk):
    """Enhanced admin view to approve a pilot"""
    if request.method != 'POST':
        return redirect('pilots:admin_verify_pilot_detail', pk=pk)
        
    pilot = get_object_or_404(Pilot, pk=pk)
    
    if pilot.status != 'pending_approval':
        messages.error(request, "This pilot is not pending approval.")
        return redirect('pilots:admin_verify_pilot_detail', pk=pk)
    
    success = _approve_pilot(request, pilot)
    
    if success:
        messages.success(request, f"Pilot '{pilot.title}' has been approved and published.")
        return redirect('pilots:admin_verify_pilots')
    else:
        messages.error(request, "Error approving pilot.")
        return redirect('pilots:admin_verify_pilot_detail', pk=pk)

@login_required
@staff_member_required
def admin_reject_pilot(request, pk):
    """Enhanced admin view to reject a pilot with detailed feedback"""
    if request.method != 'POST':
        return redirect('pilots:admin_verify_pilot_detail', pk=pk)
    
    pilot = get_object_or_404(Pilot, pk=pk)
    
    if pilot.status != 'pending_approval':
        messages.error(request, "This pilot is not pending approval.")
        return redirect('pilots:admin_verify_pilot_detail', pk=pk)
    
    feedback = request.POST.get('feedback', '')
    
    if not feedback.strip():
        messages.error(request, "Feedback is required when rejecting a pilot.")
        return redirect('pilots:admin_verify_pilot_detail', pk=pk)
    
    # Update pilot status back to draft
    pilot.status = 'draft'
    pilot.save()
    
    # Create detailed notification for enterprise with feedback
    create_pilot_notification(
        pilot=pilot,
        notification_type='pilot_rejected',
        title=f"Pilot needs revision: {pilot.title}",
        message=f"Your pilot '{pilot.title}' needs revision before it can be published.\n\nAdmin feedback: {feedback}\n\nPlease address these issues and resubmit for approval."
    )
    
    # Notify all users in the organization
    for user in pilot.organization.users.all():
        create_notification(
            recipient=user,
            notification_type='pilot_rejected',
            title=f"Pilot Revision Required: {pilot.title}",
            message=f"Your pilot '{pilot.title}' requires revision. Please check the pilot details for specific feedback.",
            related_pilot=pilot
        )
    
    messages.success(request, f"Pilot '{pilot.title}' has been rejected with feedback.")
    return redirect('pilots:admin_verify_pilots')

def _approve_pilot(request, pilot):
    """Helper function to approve a pilot with all necessary steps"""
    try:
        # Update pilot status and verification fields
        pilot.status = 'published'
        pilot.verified = True
        pilot.admin_verified_at = timezone.now()
        pilot.admin_verified_by = request.user
        pilot.published_at = timezone.now()
        pilot.save()
        
        # Create notification for enterprise
        create_pilot_notification(
            pilot=pilot,
            notification_type='pilot_approved',
            title=f"Pilot approved: {pilot.title}",
            message=f"Congratulations! Your pilot '{pilot.title}' has been approved and is now visible to startups on the platform."
        )
        
        # Notify all users in the organization
        for user in pilot.organization.users.all():
            create_notification(
                recipient=user,
                notification_type='pilot_approved',
                title=f"Pilot Published: {pilot.title}",
                message=f"Your pilot '{pilot.title}' is now live and visible to startups.",
                related_pilot=pilot
            )
        
        return True
    except Exception as e:
        print(f"Error approving pilot: {e}")
        return False

@login_required
@staff_member_required
def admin_mark_bid_as_live(request, pk):
    """Enhanced admin function to mark bid as live"""
    if request.method != 'POST':
        return redirect('admin:pilots_pilotbid_change', object_id=pk)
    
    bid = get_object_or_404(PilotBid, pk=pk)
    
    success = bid.mark_as_live()
    
    if success:
        messages.success(request, f"Bid for '{bid.pilot.title}' is now live. Both parties have been notified.")
    else:
        messages.error(request, f"Unable to mark bid as live. Current status: {bid.get_status_display()}")
    
    return redirect('admin:pilots_pilotbid_change', object_id=pk)