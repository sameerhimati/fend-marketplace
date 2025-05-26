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

class PilotListView(OrganizationRequiredMixin, LoginRequiredMixin, ListView):
    model = Pilot
    template_name = 'pilots/pilot_list.html'
    context_object_name = 'pilots'

    def get_queryset(self):
        if not hasattr(self.request.user, 'organization') or self.request.user.organization is None:
            return Pilot.objects.none()  # Return empty queryset
            
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
            raise PermissionDenied("You don't have permission to view this pilot")
        elif user_org.type == 'enterprise' and pilot.organization != user_org:
            raise PermissionDenied("You don't have permission to view this pilot")
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
def create_bid(request, pilot_id):
    """Enhanced bid creation with better validation and notifications"""
    pilot = get_object_or_404(Pilot, id=pilot_id, status='published', is_private=False)
    user_org = request.user.organization
    
    # Only startups can create bids
    if user_org.type != 'startup':
        messages.error(request, "Only startups can submit bids")
        return redirect('pilots:detail', pk=pilot_id)
    
    # Check if startup already has ANY bid for this pilot (including declined ones)
    existing_bid = PilotBid.objects.filter(
        pilot=pilot, 
        startup=user_org
    ).first()
    
    # If there's an existing declined bid, we'll update it instead of creating a new one
    is_resubmission = existing_bid and existing_bid.status == 'declined'
    
    if existing_bid and not is_resubmission:
        messages.info(request, "You already have an active bid for this pilot")
        return redirect('pilots:bid_detail', pk=existing_bid.pk)
    
    if request.method == 'POST':
        form = PilotBidForm(request.POST, instance=existing_bid if is_resubmission else None)
        if form.is_valid():
            bid_amount = form.cleaned_data['amount']
            
            # Enhanced validation
            if bid_amount <= 0:
                messages.error(request, "Bid amount must be greater than zero")
                return render(request, 'pilots/bid_form.html', {
                    'form': form,
                    'pilot': pilot,
                    'is_resubmission': is_resubmission
                })
            
            bid = form.save(commit=False)
            bid.pilot = pilot
            bid.startup = user_org
            bid.startup_fee_percentage = 5.00
            bid.enterprise_fee_percentage = 5.00 
            bid.fee_percentage = 10.00
            
            # If this is a resubmission, make sure we reset the status to pending
            if is_resubmission:
                bid.status = 'pending'
                
            bid.save()
            
            # Enhanced notification
            create_bid_notification(
                bid=bid,
                notification_type='bid_submitted',
                title=f"{'New' if not is_resubmission else 'Revised'} bid received: {pilot.title}",
                message=f"{user_org.name} has submitted a {'new' if not is_resubmission else 'revised'} bid of ${bid.amount} for your pilot '{pilot.title}'. Amount includes platform fees."
            )

            messages.success(request, f"Your bid has been {'submitted' if not is_resubmission else 'resubmitted'} successfully")
            return redirect('pilots:bid_detail', pk=bid.pk)
    else:
        # For GET requests, pre-populate with existing bid data if it's a resubmission
        initial_data = {
            'pilot': pilot,
            'amount': existing_bid.amount if is_resubmission else pilot.price,
            'proposal': existing_bid.proposal if is_resubmission else ''
        }
        form = PilotBidForm(initial=initial_data, instance=existing_bid if is_resubmission else None)
    
    return render(request, 'pilots/bid_form.html', {
        'form': form,
        'pilot': pilot,
        'is_resubmission': is_resubmission
    })

class BidListView(LoginRequiredMixin, ListView):
    """Enhanced view for listing bids with better organization"""
    model = PilotBid
    template_name = 'pilots/bid_list.html'
    context_object_name = 'bids'
    
    def get_queryset(self):
        user_org = self.request.user.organization
        if user_org.type == 'startup':
            # Startups see their submitted bids
            return PilotBid.objects.filter(startup=user_org).select_related(
                'pilot__organization'
            ).order_by('-created_at')
        elif user_org.type == 'enterprise':
            # Enterprises see bids received on their pilots
            return PilotBid.objects.filter(pilot__organization=user_org).select_related(
                'startup', 'pilot'
            ).order_by('-created_at')
        return PilotBid.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_org = self.request.user.organization
        
        if user_org.type == 'startup':
            # Separate approved and other bids
            all_bids = self.get_queryset()
            context['approved_bids'] = all_bids.filter(status__in=['approved', 'live', 'completed'])
            context['other_bids'] = all_bids.exclude(status__in=['approved', 'live', 'completed'])
        else:
            # For enterprises, group by pilot with counts
            all_bids = self.get_queryset()
            context['grouped_bids'] = {}
            
            for bid in all_bids:
                if bid.pilot_id not in context['grouped_bids']:
                    context['grouped_bids'][bid.pilot_id] = {
                        'pilot': bid.pilot,
                        'approved_bids': [],
                        'other_bids': [],
                        'total_bids': 0
                    }
                
                context['grouped_bids'][bid.pilot_id]['total_bids'] += 1
                
                if bid.status in ['approved', 'live', 'completed']:
                    context['grouped_bids'][bid.pilot_id]['approved_bids'].append(bid)
                else:
                    context['grouped_bids'][bid.pilot_id]['other_bids'].append(bid)
        
        context['is_enterprise'] = user_org.type == 'enterprise'
        return context

class BidDetailView(LoginRequiredMixin, DetailView):
    """Enhanced bid detail view with comprehensive workflow context"""
    model = PilotBid
    template_name = 'pilots/bid_detail.html'
    context_object_name = 'bid'
    
    def get_object(self, queryset=None):
        bid = super().get_object(queryset)
        user_org = self.request.user.organization
        
        # Permission check - only relevant parties can view
        if user_org not in [bid.startup, bid.pilot.organization]:
            messages.error(self.request, "You don't have permission to view this bid")
            raise PermissionDenied("Access denied")
        
        return bid

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_org = self.request.user.organization
        bid = self.object
        
        # User role context
        context['is_enterprise'] = user_org == bid.pilot.organization
        context['is_startup'] = user_org == bid.startup
        
        # Enhanced action permissions based on current status and user role
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

@login_required
def update_bid_status(request, pk):
    """Enhanced bid status updates with comprehensive validation"""
    if request.method != 'POST':
        return redirect('pilots:bid_detail', pk=pk)
    
    bid = get_object_or_404(PilotBid, pk=pk)
    user_org = request.user.organization
    
    # Check permissions - only enterprise can update bid status
    if user_org != bid.pilot.organization:
        messages.error(request, "You don't have permission to update this bid")
        return redirect('pilots:bid_detail', pk=pk)
    
    action = request.POST.get('action')
    
    if action == 'approve':
        success = bid.approve_bid()
        if success:
            messages.success(request, f"Bid approved! An invoice will be sent and you'll be notified when payment is verified.")
        else:
            messages.error(request, "Unable to approve bid at this time.")
    
    elif action == 'decline':
        success = bid.decline_bid(declined_by_enterprise=True)
        if success:
            messages.success(request, "Bid has been declined.")
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
    
    return redirect('pilots:bid_detail', pk=pk)

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
        return redirect('pilots:bid_detail', pk=bid_id)
    
    success = bid.request_completion()
    
    if success:
        messages.success(request, "Completion verification requested. The enterprise will review your work.")
    else:
        messages.error(request, "Unable to request completion at this time.")
    
    return redirect('pilots:bid_detail', pk=bid_id)

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
        return redirect('pilots:bid_detail', pk=bid_id)
    
    success = bid.verify_completion()
    
    if success:
        messages.success(request, "Work completion verified! Payment will be released to the startup by the Fend team.")
    else:
        messages.error(request, "Unable to verify completion at this time.")
    
    return redirect('pilots:bid_detail', pk=bid_id)

@login_required
def delete_bid(request, pk):
    """Allow startup to withdraw their pending bid"""
    if request.method != 'POST':
        return redirect('pilots:bid_detail', pk=pk)
    
    bid = get_object_or_404(PilotBid, pk=pk)
    user_org = request.user.organization
    
    # Check permissions - only startup can withdraw their own bid
    if user_org != bid.startup:
        messages.error(request, "You don't have permission to withdraw this bid")
        return redirect('pilots:bid_detail', pk=pk)
    
    # Only allow withdrawal of pending bids
    if bid.status != 'pending':
        messages.error(request, "Only pending bids can be withdrawn")
        return redirect('pilots:bid_detail', pk=pk)
    
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
    
    return redirect('pilots:bid_list')

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
# ADMIN VIEWS - Pilot Approval Workflow
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