from django.views.generic import TemplateView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum, Q
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from datetime import timedelta
import csv

from apps.pilots.models import Pilot, PilotBid
from apps.organizations.models import Organization
from apps.payments.models import EscrowPayment, Subscription, Payment
from apps.users.models import User

class LandingPageView(TemplateView):
    template_name = 'landing.html'
    
    def get(self, request, *args, **kwargs):
        # If user is authenticated, redirect to dashboard
        if request.user.is_authenticated and hasattr(request.user, 'organization'):
            return redirect('organizations:dashboard')

        return super().get(request, *args, **kwargs)
    
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


@staff_member_required
def enhanced_admin_dashboard(request):
    """
    Streamlined operations dashboard - core queues only
    """
    from datetime import timedelta
    
    # Calculate SLA boundaries
    today = timezone.now().date()
    sla_cutoff = timezone.now() - timedelta(hours=24)
    
    # STEP 1: Generate Mercury Invoices (approved bids without escrow payment)
    approved_bids = PilotBid.objects.filter(
        status='approved',
        payment_holding_service__isnull=True
    ).select_related('pilot', 'startup')
    invoices_to_generate = approved_bids.count()
    overdue_invoices = approved_bids.filter(updated_at__lt=sla_cutoff).count()
    
    # STEP 2: Check Mercury for Wire Transfers (invoices sent, payment pending)
    check_mercury_payments = EscrowPayment.objects.filter(
        status='instructions_sent'
    ).count()
    overdue_mercury = EscrowPayment.objects.filter(
        status='instructions_sent',
        created_at__lt=sla_cutoff
    ).count()
    
    # STEP 3: Release Funds to Startups (work completed, payment received)
    release_funds = EscrowPayment.objects.filter(
        status='received',
        pilot_bid__status='completed'
    ).count()
    overdue_releases = EscrowPayment.objects.filter(
        status='received',
        pilot_bid__status='completed',
        pilot_bid__updated_at__lt=sla_cutoff
    ).count()
    
    # Secondary: Organization approvals
    pending_approvals = Organization.objects.filter(approval_status='pending')
    pending_approvals_count = pending_approvals.count()
    overdue_approvals = pending_approvals.filter(created_at__lt=sla_cutoff).count()
    
    # Secondary: Pilot verifications
    pending_pilots = Pilot.objects.filter(status='pending_approval')
    pilot_count_pending = pending_pilots.count()
    overdue_pilots = pending_pilots.filter(created_at__lt=sla_cutoff).count()
    
    
    # Calculate overdue items total
    overdue_items = overdue_invoices + overdue_mercury + overdue_releases + overdue_approvals + overdue_pilots
    
    # Active work counts
    active_pilots_count = PilotBid.objects.filter(status='live').count()
    completion_pending_count = PilotBid.objects.filter(status='completion_pending').count()
    
    # Performance metrics (actionable only)
    total_queue_depth = invoices_to_generate + check_mercury_payments + release_funds + pending_approvals_count + pilot_count_pending
    
    context = {
        # 3-step Mercury workflow
        'invoices_to_generate': invoices_to_generate,
        'check_mercury_payments': check_mercury_payments,
        'release_funds': release_funds,
        
        # Secondary queues
        'pending_approvals_count': pending_approvals_count,
        'pilot_count_pending': pilot_count_pending,
        
        # SLA tracking
        'overdue_items': overdue_items,
        
        # Performance metrics
        'total_queue_depth': total_queue_depth,
        
        # Active work counts
        'active_pilots_count': active_pilots_count,
        'completion_pending_count': completion_pending_count,
    }
    
    return render(request, 'admin/index.html', context)


@staff_member_required
def admin_org_dashboard(request):
    """
    Organization management dashboard
    """
    # Pending approvals (top priority)
    pending_orgs = Organization.objects.filter(
        approval_status='pending'
    ).order_by('-created_at')
    
    # All organizations with search functionality
    search = request.GET.get('search', '')
    org_type_filter = request.GET.get('type', 'all')
    
    all_orgs = Organization.objects.all()
    
    if search:
        all_orgs = all_orgs.filter(
            Q(name__icontains=search) |
            Q(primary_contact_name__icontains=search) |
            Q(business_registration_number__icontains=search)
        )
    
    if org_type_filter != 'all':
        all_orgs = all_orgs.filter(type=org_type_filter)
    
    all_orgs = all_orgs.order_by('-created_at')
    
    # Stats
    total_orgs = Organization.objects.count()
    enterprises = Organization.objects.filter(type='enterprise').count()
    startups = Organization.objects.filter(type='startup').count()
    pending_count = pending_orgs.count()
    
    context = {
        'pending_orgs': pending_orgs,
        'all_orgs': all_orgs,
        'search': search,
        'org_type_filter': org_type_filter,
        'total_orgs': total_orgs,
        'enterprises': enterprises,
        'startups': startups,
        'pending_count': pending_count,
    }
    
    return render(request, 'admin/org_dashboard.html', context)


@staff_member_required  
def admin_pilot_dashboard(request):
    """
    Pilot management dashboard
    """
    # Pending approvals (top priority)
    pending_pilots = Pilot.objects.filter(
        status='pending_approval'
    ).select_related('organization').order_by('-created_at')
    
    # All pilots with search functionality
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    
    all_pilots = Pilot.objects.select_related('organization')
    
    if search:
        all_pilots = all_pilots.filter(
            Q(title__icontains=search) |
            Q(organization__name__icontains=search) |
            Q(description__icontains=search)
        )
    
    if status_filter != 'all':
        all_pilots = all_pilots.filter(status=status_filter)
    
    all_pilots = all_pilots.order_by('-created_at')
    
    # Stats
    total_pilots = Pilot.objects.count()
    published = Pilot.objects.filter(status='published').count()
    in_progress = Pilot.objects.filter(status='in_progress').count()
    completed = Pilot.objects.filter(status='completed').count()
    pending_count = pending_pilots.count()
    
    context = {
        'pending_pilots': pending_pilots,
        'all_pilots': all_pilots,
        'search': search,
        'status_filter': status_filter,
        'total_pilots': total_pilots,
        'published': published,
        'in_progress': in_progress,
        'completed': completed,
        'pending_count': pending_count,
    }
    
    return render(request, 'admin/pilot_dashboard.html', context)


@staff_member_required
def admin_org_detail(request, org_id):
    """
    Organization detail view showing all registration info and promotions
    """
    org = get_object_or_404(Organization, id=org_id)
    
    # Get related data
    pilots = org.pilots.all().order_by('-created_at')[:10]  # Recent pilots
    users = org.users.all()  # Organization users
    subscription = getattr(org, 'subscription', None)  # Subscription info
    
    # Get payments related to this org
    if org.type == 'enterprise':
        # For enterprises, get pilots they've posted and payments made
        enterprise_payments = EscrowPayment.objects.filter(
            pilot_bid__pilot__organization=org
        ).order_by('-created_at')[:5]
        startup_payments = None
    else:
        # For startups, get bids they've made and payments received
        startup_payments = EscrowPayment.objects.filter(
            pilot_bid__startup=org
        ).order_by('-created_at')[:5]
        enterprise_payments = None
    
    context = {
        'org': org,
        'pilots': pilots,
        'users': users,
        'subscription': subscription,
        'enterprise_payments': enterprise_payments,
        'startup_payments': startup_payments,
    }
    
    return render(request, 'admin/org_detail.html', context)


@staff_member_required
def admin_org_edit(request, org_id):
    """
    Edit organization details
    """
    from django.contrib import messages
    
    org = get_object_or_404(Organization, id=org_id)
    
    if request.method == 'POST':
        try:
            # Update basic information
            org.name = request.POST.get('name', org.name)
            org.website = request.POST.get('website', org.website)
            org.description = request.POST.get('description', '')
            org.employee_count = request.POST.get('employee_count', '')
            
            # Handle founding year
            founding_year = request.POST.get('founding_year', '')
            if founding_year:
                org.founding_year = int(founding_year)
            else:
                org.founding_year = None
                
            org.headquarters_location = request.POST.get('headquarters_location', '')
            
            # Update contact information
            org.primary_contact_name = request.POST.get('primary_contact_name', '')
            org.country_code = request.POST.get('country_code', '+1')
            org.primary_contact_phone = request.POST.get('primary_contact_phone', '')
            
            # Update legal information
            org.business_type = request.POST.get('business_type', '')
            org.business_registration_number = request.POST.get('business_registration_number', '')
            org.tax_identification_number = request.POST.get('tax_identification_number', '')
            
            # Update social media
            org.linkedin_url = request.POST.get('linkedin_url', '')
            org.twitter_url = request.POST.get('twitter_url', '')
            
            # Save the changes
            org.save()
            
            messages.success(request, f'Organization "{org.name}" has been updated successfully.')
            return redirect('admin_org_detail', org_id=org.id)
            
        except Exception as e:
            messages.error(request, f'Error updating organization: {str(e)}')
    
    context = {
        'org': org,
    }
    
    return render(request, 'admin/org_edit.html', context)


@staff_member_required
def admin_global_search(request):
    """
    Global search across all models for operations team
    """
    query = request.GET.get('q', '').strip()
    
    if not query:
        return JsonResponse({'results': []})
    
    results = []
    
    # Search organizations
    organizations = Organization.objects.filter(
        Q(name__icontains=query) |
        Q(primary_contact_name__icontains=query) |
        Q(users__email__icontains=query) |
        Q(business_registration_number__icontains=query)
    ).distinct()[:5]
    
    for org in organizations:
        results.append({
            'type': 'Organization',
            'title': org.name,
            'subtitle': f"{org.get_type_display()} - {org.get_approval_status_display()}",
            'url': f'/admin/organizations/organization/{org.id}/change/',
            'icon': 'fas fa-building'
        })
    
    # Search pilots
    pilots = Pilot.objects.filter(
        Q(title__icontains=query) |
        Q(description__icontains=query) |
        Q(organization__name__icontains=query)
    ).select_related('organization')[:5]
    
    for pilot in pilots:
        results.append({
            'type': 'Pilot',
            'title': pilot.title,
            'subtitle': f"{pilot.organization.name} - {pilot.get_status_display()}",
            'url': f'/admin/pilots/pilot/{pilot.id}/change/',
            'icon': 'fas fa-rocket'
        })
    
    # Search payments
    payments = EscrowPayment.objects.filter(
        Q(reference_code__icontains=query) |
        Q(pilot_bid__pilot__title__icontains=query) |
        Q(pilot_bid__startup__name__icontains=query)
    ).select_related('pilot_bid__pilot', 'pilot_bid__startup')[:5]
    
    for payment in payments:
        results.append({
            'type': 'Payment',
            'title': f"Payment {payment.reference_code}",
            'subtitle': f"${payment.total_amount} - {payment.get_status_display()}",
            'url': f'/admin/payments/escrowpayment/{payment.id}/change/',
            'icon': 'fas fa-credit-card'
        })
    
    return JsonResponse({'results': results[:15]})


@staff_member_required
def admin_export_csv(request):
    """
    Export data for various reports
    """
    export_type = request.GET.get('type', 'payments')
    
    if export_type == 'payments':
        return _export_payments_csv()
    elif export_type == 'organizations':
        return _export_organizations_csv()
    elif export_type == 'pilots':
        return _export_pilots_csv()
    else:
        return HttpResponse('Invalid export type', status=400)


def _export_payments_csv():
    """Export payments data as CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="fend_payments_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Reference Code', 'Pilot Title', 'Enterprise', 'Startup', 
        'Total Amount', 'Status', 'Created', 'Released'
    ])
    
    payments = EscrowPayment.objects.select_related(
        'pilot_bid__pilot__organization',
        'pilot_bid__startup'
    ).order_by('-created_at')
    
    for payment in payments:
        writer.writerow([
            payment.reference_code,
            payment.pilot_bid.pilot.title,
            payment.pilot_bid.pilot.organization.name,
            payment.pilot_bid.startup.name,
            payment.total_amount,
            payment.get_status_display(),
            payment.created_at.strftime('%Y-%m-%d'),
            payment.released_at.strftime('%Y-%m-%d') if payment.released_at else '',
        ])
    
    return response


def _export_organizations_csv():
    """Export organizations data as CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="fend_organizations_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Name', 'Type', 'Approval Status', 'Primary Contact', 'Created'
    ])
    
    organizations = Organization.objects.order_by('-created_at')
    
    for org in organizations:
        writer.writerow([
            org.name,
            org.get_type_display(),
            org.get_approval_status_display(),
            org.primary_contact_name or '',
            org.created_at.strftime('%Y-%m-%d'),
        ])
    
    return response


def _export_pilots_csv():
    """Export pilots data as CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="fend_pilots_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Title', 'Organization', 'Status', 'Price', 'Created'
    ])
    
    pilots = Pilot.objects.select_related('organization').order_by('-created_at')
    
    for pilot in pilots:
        writer.writerow([
            pilot.title,
            pilot.organization.name,
            pilot.get_status_display(),
            pilot.price,
            pilot.created_at.strftime('%Y-%m-%d'),
        ])
    
    return response