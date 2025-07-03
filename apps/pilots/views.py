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
            )
            
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
            
            # Combine querysets
            pilots = available_pilots.union(bid_pilots)
            
        else:
            return Pilot.objects.none()
        
        # Apply search filters
        search_query = self.request.GET.get('search', '').strip()
        status_filter = self.request.GET.get('status', '').strip()
        
        if search_query:
            # Search across title, description, and organization name
            pilots = pilots.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(organization__name__icontains=search_query)
            )
        
        if status_filter and status_filter != 'all':
            pilots = pilots.filter(status=status_filter)
        
        # Order by relevance (search match) then by creation date
        if search_query:
            # Boost exact title matches, then partial title matches, then description matches
            pilots = pilots.extra(
                select={
                    'relevance': """
                        CASE 
                            WHEN LOWER(title) = LOWER(%s) THEN 3
                            WHEN LOWER(title) LIKE LOWER(%s) THEN 2
                            WHEN LOWER(description) LIKE LOWER(%s) THEN 1
                            ELSE 0
                        END
                    """
                },
                select_params=[search_query, f'%{search_query}%', f'%{search_query}%']
            ).order_by('-relevance', '-created_at')
        else:
            pilots = pilots.order_by('-created_at')
            
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
        
        # Add search context
        context['search_query'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['has_filters'] = bool(context['search_query'] or context['status_filter'])
        
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

    def dispatch(self, request, *args, **kwargs):
        # Only enterprise users can create pilots
        if request.user.organization.type != 'enterprise':
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.organization = self.request.user.organization
        form.instance.status = 'draft'  # Default to draft status
        
        # Handle different save actions
        if 'save_draft' in self.request.POST:
            response = super().form_valid(form)
            messages.success(
                self.request, 
                f'Pilot "{form.instance.title}" has been saved as a draft. You can continue editing anytime.'
            )
            return response
        else:
            # Regular save or attempt submission
            response = super().form_valid(form)
            pilot = form.instance
            
            # For new pilot creation, just save as draft without confusing validation notifications
            # The user will see proper validation on the pilot detail page if they want to submit later
            messages.success(
                self.request,
                f'Pilot "{pilot.title}" has been created successfully. You can continue editing and submit for review when ready.'
            )
            
            return response
    
    def get_success_url(self):
        return reverse('pilots:detail', kwargs={'pk': self.object.pk})

class PilotUpdateView(LoginRequiredMixin, UpdateView):
    model = Pilot
    form_class = PilotForm
    template_name = 'pilots/pilot_form.html'
    context_object_name = 'pilot'
    
    def dispatch(self, request, *args, **kwargs):
        pilot = self.get_object()
        if not pilot.can_be_edited_by(request.user):
            messages.error(
                request, 
                f"You don't have permission to edit this pilot. Only the pilot owner can make changes while it's in {pilot.get_status_display()} status."
            )
            return redirect('pilots:detail', pk=pilot.pk)
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        # Handle different save actions
        if 'save_draft' in self.request.POST:
            response = super().form_valid(form)
            messages.success(
                self.request, 
                f'✅ Your changes to "{form.instance.title}" have been saved successfully.'
            )
            return response
        else:
            # Regular save or attempt submission
            response = super().form_valid(form)
            pilot = form.instance
            
            # If still in draft and trying to submit
            if pilot.status == 'draft':
                # Check if pilot is complete enough for submission
                missing_fields = []
                if not (pilot.technical_specs_doc or pilot.technical_specs_text):
                    missing_fields.append("Technical Specifications")
                if not (pilot.performance_metrics_doc or pilot.performance_metrics):
                    missing_fields.append("Performance Metrics")
                if not (pilot.compliance_requirements_doc or pilot.compliance_requirements):
                    missing_fields.append("Compliance Requirements")
                
                if missing_fields:
                    messages.warning(
                        self.request,
                        f'⚠️ Changes saved! To submit "{pilot.title}" for review, please complete: {", ".join(missing_fields)}'
                    )
                else:
                    # Attempt to publish
                    try:
                        from .models import publish_pilot
                        success = publish_pilot(pilot, self.request.user)
                        if success:
                            messages.success(
                                self.request,
                                f'🎉 "{pilot.title}" has been submitted for review! You\'ll be notified when it\'s approved.'
                            )
                        else:
                            messages.success(
                                self.request,
                                f'✅ Changes to "{pilot.title}" have been saved successfully.'
                            )
                    except Exception as e:
                        messages.success(
                            self.request,
                            f'✅ Changes to "{pilot.title}" have been saved successfully.'
                        )
            else:
                messages.success(
                    self.request,
                    f'✅ Changes to "{pilot.title}" have been saved successfully.'
                )
            
            return response
    
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
                title=f"👀 Under Review: {bid.pilot.title}",
                message=f"Your bid for '{bid.pilot.title}' is now being reviewed by {bid.pilot.organization.name}."
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
            
            # Check legal document acceptances for startups
            organization = request.user.organization
            if not organization.has_required_legal_acceptances():
                missing_docs = []
                if not organization.terms_of_service_accepted:
                    missing_docs.append("Terms of Service")
                if not organization.privacy_policy_accepted:
                    missing_docs.append("Privacy Policy")
                if not organization.user_agreement_accepted:
                    missing_docs.append("User Agreement")
                
                messages.error(request, f"You must accept the following legal documents before submitting bids: {', '.join(missing_docs)}")
                return render(request, 'pilots/bid_form.html', {
                    'form': form,
                    'pilot': pilot,
                    'is_resubmission': is_resubmission,
                    'is_edit': can_edit
                })
            
            # Validate current legal agreement acceptance (checkbox on form)
            if not request.POST.get('accept_legal_terms'):
                messages.error(request, "You must accept the legal agreement to submit this bid.")
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
                title=f"💼 {'Revised' if (is_resubmission or can_edit) else 'New'} Bid: {pilot.title}",
                message=f"{user_org.name} submitted a {action_text} ${bid.amount} bid for '{pilot.title}'."
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
        title=f"🚫 Bid Withdrawn: {bid.pilot.title}",
        message=f"{bid.startup.name} withdrew their ${bid.amount} bid for '{bid.pilot.title}'."
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
    
    # Check if organization is approved
    organization = pilot.organization
    if organization.approval_status != 'approved':
        messages.error(request, "You must be approved before you can publish pilots.")
        return redirect('pilots:detail', pk=pk)
    
    # Validate current legal agreement acceptance (checkbox on form)
    legal_agreement_accepted = request.POST.get('legal_agreement_accepted') == 'on'
    if not legal_agreement_accepted:
        messages.error(request, "You must accept the legal agreement to publish this pilot.")
        return redirect('pilots:detail', pk=pk)
    
    # Auto-accept payment legal documents when checkbox is checked
    if not organization.payment_terms_accepted:
        organization.accept_legal_document('payment_terms')
    if not organization.payment_holding_agreement_accepted:
        organization.accept_legal_document('payment_holding_agreement')
    
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
    """Enhanced admin view for pilot verification dashboard - shows all pilots"""
    # Get pilots that need attention first (pending approval)
    pending_pilots = Pilot.objects.filter(
        status='pending_approval'
    ).select_related(
        'organization'
    ).prefetch_related(
        'organization__users'
    ).order_by('-updated_at')
    
    # Get all other pilots (published, draft, in_progress, completed, cancelled)
    other_pilots = Pilot.objects.exclude(
        status='pending_approval'
    ).select_related(
        'organization'
    ).prefetch_related(
        'organization__users'
    ).order_by('-updated_at')
    
    # Get stats for the dashboard
    verified_today = Pilot.objects.filter(
        status='published', 
        published_at__date=timezone.now().date()
    ).count()
    
    total_verified = Pilot.objects.filter(status='published').count()
    
    # Handle bulk actions
    if request.method == 'POST':
        action = request.POST.get('action')
        pilot_ids = request.POST.getlist('pilot_ids')
        
        if action == 'bulk_approve' and pilot_ids:
            pilots = Pilot.objects.filter(id__in=pilot_ids, status='pending_approval')
            approved_count = 0
            for pilot in pilots:
                if _approve_pilot(request, pilot):
                    approved_count += 1
            messages.success(request, f"{approved_count} pilots approved successfully.")
        elif action == 'export' and pilot_ids:
            # Simple CSV export functionality
            import csv
            from django.http import HttpResponse
            
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="pilots_export.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['ID', 'Title', 'Organization', 'Status', 'Price', 'Created', 'Updated'])
            
            pilots = Pilot.objects.filter(id__in=pilot_ids).select_related('organization')
            for pilot in pilots:
                writer.writerow([
                    pilot.id,
                    pilot.title,
                    pilot.organization.name,
                    pilot.get_status_display(),
                    pilot.price,
                    pilot.created_at.strftime('%Y-%m-%d %H:%M'),
                    pilot.updated_at.strftime('%Y-%m-%d %H:%M')
                ])
            return response
        elif not action:
            messages.error(request, "Please select an action.")
        elif not pilot_ids:
            messages.error(request, "Please select at least one pilot.")
        
        # Refresh querysets after actions
        pending_pilots = Pilot.objects.filter(
            status='pending_approval'
        ).select_related('organization').order_by('-updated_at')
        other_pilots = Pilot.objects.exclude(
            status='pending_approval'
        ).select_related('organization').order_by('-updated_at')
    
    context = {
        'title': 'Pilot Verification - All Pilots',
        'pending_pilots': pending_pilots,
        'other_pilots': other_pilots,
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
        # Update pilot status (admin approval bypasses subscription limits)
        pilot.status = 'published'
        pilot.published_at = timezone.now()
        # Set flag to bypass subscription validation for admin approval
        pilot._admin_approval = True
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