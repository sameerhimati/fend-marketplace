from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
import csv
from apps.notifications.services import create_bid_notification, create_pilot_notification, create_notification

from .models import PricingPlan, Subscription, Payment, EscrowPayment, EscrowPaymentLog
from apps.pilots.models import PilotBid
from apps.organizations.models import Organization

import stripe
import json
from datetime import datetime, timedelta

# Set your Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY

@login_required
def payment_selection(request):
    """Show payment plan selection after registration"""
    # Get the user's organization, handle case when it doesn't exist
    organization = getattr(request.user, 'organization', None)
    
    # If user has no organization, redirect to register
    if not organization:
        messages.error(request, "You need to complete registration first.")
        return redirect('organizations:register')
    
    # If organization already has active subscription, redirect to dashboard
    try:
        if organization.has_active_subscription():
            return redirect('organizations:dashboard')
    except Exception as e:
        # Handle any unexpected errors during subscription check
        print(f"Error checking subscription: {e}")
        # Continue to plan selection as a fallback
    
    # Get available plans based on organization type
    available_plans = PricingPlan.get_available_plans(organization.type)
    
    # Sort plans - monthly first, yearly second
    sorted_plans = sorted(available_plans, key=lambda p: 0 if p.billing_frequency == 'monthly' else 1)
    
    if request.method == 'POST':
        plan_id = request.POST.get('plan_id')
        
        if not plan_id:
            messages.error(request, "Please select a plan")
            return render(request, 'payments/plan_selection.html', {
                'plans': sorted_plans,
                'organization': organization
            })
        
        # Get the selected plan
        plan = get_object_or_404(PricingPlan, id=plan_id)
        
        # Create or get the subscription
        subscription, created = Subscription.objects.get_or_create(
            organization=organization,
            defaults={
                'plan': plan,
                'stripe_customer_id': organization.stripe_customer_id or '',
                'status': 'incomplete'
            }
        )
        
        if not created:
            # Update existing subscription with new plan
            subscription.plan = plan
            subscription.save()
        
        # Create Stripe Checkout Session
        try:
            checkout_session = create_checkout_session(request, organization, plan, subscription)
            return redirect(checkout_session.url)
        except Exception as e:
            messages.error(request, f"Error creating checkout session: {str(e)}")
            return render(request, 'payments/plan_selection.html', {
                'plans': sorted_plans,
                'organization': organization
            })
    
    return render(request, 'payments/plan_selection.html', {
        'plans': sorted_plans,
        'organization': organization
    })

def create_checkout_session(request, organization, plan, subscription):
    """Create a Stripe Checkout Session for the selected plan"""
    # Create the price in Stripe if needed
    if not plan.stripe_price_id:
        # Handle the billing frequency conversion to Stripe format
        stripe_interval = None
        if plan.billing_frequency == 'monthly':
            stripe_interval = 'month'
        elif plan.billing_frequency == 'yearly':
            stripe_interval = 'year'
        
        # Create the Stripe price object
        if plan.billing_frequency != 'one_time' and stripe_interval:
            price = stripe.Price.create(
                unit_amount=int(plan.price * 100),  # Convert to cents
                currency="usd",
                recurring={"interval": stripe_interval},
                product_data={"name": plan.name},
            )
        else:
            # For one-time payments
            price = stripe.Price.create(
                unit_amount=int(plan.price * 100),  # Convert to cents
                currency="usd",
                product_data={"name": plan.name},
            )
            
        plan.stripe_price_id = price.id
        plan.save()
    
    # Build checkout line items
    line_items = [{
        'price': plan.stripe_price_id,
        'quantity': 1,
    }]
    
    # Create a Stripe Customer if not exists
    if not organization.stripe_customer_id:
        customer = stripe.Customer.create(
            email=request.user.email,
            name=organization.name,
            metadata={
                'organization_id': organization.id,
                'organization_type': organization.type
            }
        )
        organization.stripe_customer_id = customer.id
        organization.save()
    
    # Create the checkout session with the customer ID
    checkout_session = stripe.checkout.Session.create(
        customer=organization.stripe_customer_id,
        payment_method_types=['card'],
        line_items=line_items,
        mode='subscription' if plan.billing_frequency != 'one_time' else 'payment',
        success_url=request.build_absolute_uri(
            reverse('payments:checkout_success')
        ) + f"?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=request.build_absolute_uri(
            reverse('payments:checkout_cancel')
        ),
        metadata={
            'organization_id': organization.id,
            'subscription_id': subscription.id,
            'plan_id': plan.id
        }
    )
    
    return checkout_session

@login_required
def checkout_success(request):
    """Handle successful checkout"""
    session_id = request.GET.get('session_id')
    if not session_id:
        messages.error(request, "Invalid checkout session")
        return redirect('payments:payment_selection')
    
    try:
        # Retrieve the session
        session = stripe.checkout.Session.retrieve(session_id)
        
        # Verify payment status - only proceed if payment is complete
        if session.payment_status != 'paid':
            messages.warning(request, "Your payment is still being processed. Your subscription will be activated once payment is complete.")
            return redirect('payments:subscription_detail')
        
        # Get the subscription from metadata
        organization_id = session.metadata.get('organization_id')
        subscription_id = session.metadata.get('subscription_id')
        
        if not organization_id or not subscription_id:
            messages.error(request, "Invalid checkout data")
            return redirect('payments:payment_selection')
        
        # Verify the organization matches the logged in user
        organization = get_object_or_404(Organization, id=organization_id)
        if request.user.organization.id != organization.id:
            messages.error(request, "You do not have permission to access this checkout")
            return redirect('payments:payment_selection')
        
        # Update the subscription
        subscription = get_object_or_404(Subscription, id=subscription_id)
        
        # Check if this is a plan upgrade
        upgrade_plan_id = request.session.get('upgrade_plan_id')
        if upgrade_plan_id:
            # Get the new plan
            plan = get_object_or_404(PricingPlan, id=upgrade_plan_id)
            # Update to the new plan
            subscription.plan = plan
            # Remove from session
            del request.session['upgrade_plan_id']
        
        # If subscription mode
        if session.mode == 'subscription' and session.subscription:
            stripe_subscription = stripe.Subscription.retrieve(session.subscription)
            
            subscription.stripe_subscription_id = session.subscription
            subscription.status = stripe_subscription.status
            subscription.current_period_start = datetime.fromtimestamp(stripe_subscription.current_period_start)
            subscription.current_period_end = datetime.fromtimestamp(stripe_subscription.current_period_end)
            subscription.save()
            
            # Create a payment record - use session.id if payment_intent is not available
            payment_id = session.payment_intent or session.id
            payment = Payment.objects.create(
                organization=organization,
                subscription=subscription,
                payment_type='subscription',
                amount=subscription.plan.price,
                stripe_payment_id=payment_id,
                status='complete'
            )
        
        # Mark organization as having completed payment
        organization.onboarding_completed = True
        organization.has_payment_method = True
        organization.save()
        
        messages.success(request, "Your payment was successful! Your subscription has been updated.")
        return redirect('organizations:dashboard')
        
    except Exception as e:
        messages.error(request, f"Error processing payment: {str(e)}")
        return redirect('payments:payment_selection')

@login_required
def checkout_cancel(request):
    """Handle cancelled checkout"""
    # Clear any pending plan upgrades
    if 'upgrade_plan_id' in request.session:
        del request.session['upgrade_plan_id']
    
    # Get the organization's subscription and mark it inactive if it's not already active
    organization = request.user.organization
    try:
        subscription = Subscription.objects.get(organization=organization)
        if subscription.status != 'active':
            subscription.status = 'incomplete'
            subscription.save()
    except Subscription.DoesNotExist:
        pass
    
    messages.warning(request, "Your payment was cancelled. Your subscription has not been changed.")
    return redirect('payments:subscription_detail')

@csrf_exempt
def stripe_webhook(request):
    """Handle Stripe webhook events"""
    payload = request.body
    event = None
    
    try:
        event = stripe.Event.construct_from(
            json.loads(payload), stripe.api_key
        )
    except ValueError as e:
        return HttpResponse(status=400)
    
    # Handle specific events
    if event.type == 'checkout.session.completed':
        # Payment was successful, handle accordingly
        session = event.data.object
        
        # Get metadata
        organization_id = session.metadata.get('organization_id')
        subscription_id = session.metadata.get('subscription_id')

        if organization_id and subscription_id:
            try:
                organization = Organization.objects.get(id=organization_id)
                subscription = Subscription.objects.get(id=subscription_id)
                
                # Update subscription details
                if session.mode == 'subscription' and session.subscription:
                    stripe_subscription = stripe.Subscription.retrieve(session.subscription)
                    
                    subscription.stripe_subscription_id = session.subscription
                    subscription.status = stripe_subscription.status
                    subscription.current_period_start = datetime.fromtimestamp(stripe_subscription.current_period_start)
                    subscription.current_period_end = datetime.fromtimestamp(stripe_subscription.current_period_end)
                    subscription.save()
                
                # Mark organization as having completed payment BUT still pending approval
                organization.onboarding_completed = True
                organization.has_payment_method = True
                # Keep approval_status as 'pending' for admin review
                organization.save()
                
                # Create payment record
                Payment.objects.get_or_create(
                    organization=organization,
                    subscription=subscription,
                    payment_type='subscription',
                    defaults={
                        'amount': subscription.plan.price,
                        'stripe_payment_id': session.payment_intent or session.id,
                        'status': 'complete'
                    }
                )
                
                # Notify admins about new registration
                notify_admins_of_new_registration(organization)
                
            except (Organization.DoesNotExist, Subscription.DoesNotExist) as e:
                print(f"Error processing webhook: {e}")
    
    elif event.type == 'invoice.payment_succeeded':
        # Subscription renewal was successful
        invoice = event.data.object
        
        subscription_id = invoice.subscription
        customer_id = invoice.customer
        
        try:
            # Find the organization by Stripe customer ID
            organization = Organization.objects.get(stripe_customer_id=customer_id)
            
            # Find the subscription
            subscription = Subscription.objects.get(
                organization=organization,
                stripe_subscription_id=subscription_id
            )
            
            # Update subscription details
            stripe_subscription = stripe.Subscription.retrieve(subscription_id)
            
            subscription.status = stripe_subscription.status
            subscription.current_period_start = datetime.fromtimestamp(stripe_subscription.current_period_start)
            subscription.current_period_end = datetime.fromtimestamp(stripe_subscription.current_period_end)
            subscription.save()
            
            # Create payment record
            payment = Payment.objects.create(
                organization=organization,
                subscription=subscription,
                payment_type='subscription',
                amount=invoice.amount_paid / 100.0,  # Convert from cents
                stripe_payment_id=invoice.payment_intent,
                status='complete'
            )

        except (Organization.DoesNotExist, Subscription.DoesNotExist) as e:
            print(f"Error processing invoice payment: {e}")
    
    elif event.type == 'invoice.payment_failed':
        # Subscription renewal failed
        invoice = event.data.object
        
        subscription_id = invoice.subscription
        customer_id = invoice.customer
        
        try:
            # Find the organization by Stripe customer ID
            organization = Organization.objects.get(stripe_customer_id=customer_id)
            
            # Find the subscription
            subscription = Subscription.objects.get(
                organization=organization,
                stripe_subscription_id=subscription_id
            )
            
            # Update subscription status
            subscription.status = 'past_due'
            subscription.save()
            
        except (Organization.DoesNotExist, Subscription.DoesNotExist) as e:
            print(f"Error processing invoice payment failure: {e}")
    
    elif event.type == 'customer.subscription.deleted':
        # Subscription was deleted
        stripe_subscription = event.data.object
        
        subscription_id = stripe_subscription.id
        customer_id = stripe_subscription.customer
        
        try:
            # Find the organization by Stripe customer ID
            organization = Organization.objects.get(stripe_customer_id=customer_id)
            
            # Find the subscription
            subscription = Subscription.objects.get(
                organization=organization,
                stripe_subscription_id=subscription_id
            )
            
            # Update subscription status
            subscription.status = 'canceled'
            subscription.save()
            
        except (Organization.DoesNotExist, Subscription.DoesNotExist) as e:
            print(f"Error processing subscription deletion: {e}")
    
    return HttpResponse(status=200)

def notify_admins_of_new_registration(organization):
    """Notify admin users about a new registration using in-app notifications"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    try:
        # Get admin users
        admins = User.objects.filter(is_staff=True)
        
        for admin in admins:
            # Create admin notification
            create_notification(
                recipient=admin,
                notification_type='admin_approval',
                title=f"New {organization.get_type_display()} Registration",
                message=f"{organization.name} has registered as a {organization.get_type_display().lower()} and is pending approval. Payment has been received.",
            )
    except Exception as e:
        print(f"Error creating admin notification: {e}")

@login_required
def subscription_detail(request):
    """Show subscription details page"""
    organization = request.user.organization
    
    try:
        subscription = Subscription.objects.get(organization=organization)
        
        # Get subscription payment history
        payments = Payment.objects.filter(
            organization=organization,
            subscription=subscription
        ).order_by('-created_at')[:10]  # Limit to last 10 payments
        
        return render(request, 'payments/subscription_detail.html', {
            'subscription': subscription,
            'payments': payments,
            'organization': organization,
            'has_active_subscription': organization.has_active_subscription()
        })
    except Subscription.DoesNotExist:
        messages.warning(request, "You don't have an active subscription.")
        return redirect('payments:payment_selection')

@login_required
def cancel_subscription(request):
    """Cancel the current subscription"""
    if request.method != 'POST':
        return redirect('payments:subscription_detail')
    
    organization = request.user.organization
    
    try:
        subscription = Subscription.objects.get(organization=organization)
        
        # Cancel at period end or immediately
        cancel_immediately = request.POST.get('cancel_immediately') == 'true'
        
        if subscription.stripe_subscription_id:
            if cancel_immediately:
                # Cancel immediately with prorated refund
                stripe.Subscription.delete(
                    subscription.stripe_subscription_id,
                    prorate=True
                )
                
                subscription.status = 'canceled'
                subscription.save()
                
                messages.success(request, "Your subscription has been canceled. A prorated refund will be processed.")
            else:
                # Cancel at period end
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True
                )
                
                subscription.cancel_at_period_end = True
                subscription.save()
                
                messages.success(request, "Your subscription will be canceled at the end of the current billing period.")
        else:
            # If no Stripe subscription ID (e.g., for one-time payments), cancel immediately
            subscription.status = 'canceled'
            subscription.save()
            
            messages.success(request, "Your subscription has been canceled.")
        
        return redirect('payments:subscription_detail')
    except Subscription.DoesNotExist:
        messages.warning(request, "You don't have an active subscription.")
        return redirect('payments:payment_selection')
    except Exception as e:
        messages.error(request, f"Error canceling subscription: {str(e)}")
        return redirect('payments:subscription_detail')
    
@login_required
def cancel_subscription_undo(request):
    """Undo subscription cancellation"""
    if request.method != 'POST':
        return redirect('payments:subscription_detail')
    
    organization = request.user.organization
    
    try:
        subscription = Subscription.objects.get(organization=organization)
        
        if subscription.stripe_subscription_id and subscription.cancel_at_period_end:
            # Remove cancellation schedule
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=False
            )
            
            subscription.cancel_at_period_end = False
            subscription.save()
            
            messages.success(request, "Your subscription will continue.")
        
        return redirect('payments:subscription_detail')
    except Subscription.DoesNotExist:
        messages.warning(request, "You don't have an active subscription.")
        return redirect('payments:payment_selection')
    except Exception as e:
        messages.error(request, f"Error undoing cancellation: {str(e)}")
        return redirect('payments:subscription_detail')

@login_required
def upgrade_subscription(request):
    """Upgrade or change subscription plan"""
    organization = request.user.organization
    
    # Get available plans based on organization type
    available_plans = PricingPlan.get_available_plans(organization.type)
    
    # Sort plans - monthly first, yearly second
    sorted_plans = sorted(available_plans, key=lambda p: 0 if p.billing_frequency == 'monthly' else 1)
    
    try:
        current_subscription = Subscription.objects.get(organization=organization)
        original_plan = current_subscription.plan  # Save the original plan
    except Subscription.DoesNotExist:
        return redirect('payments:payment_selection')
    
    if request.method == 'POST':
        plan_id = request.POST.get('plan_id')
        
        if not plan_id:
            messages.error(request, "Please select a plan")
            return render(request, 'payments/upgrade_subscription.html', {
                'plans': sorted_plans,
                'current_subscription': current_subscription
            })
        
        # Get the selected plan
        plan = get_object_or_404(PricingPlan, id=plan_id)
        
        # If it's the same plan, no need to change anything
        if plan.id == current_subscription.plan.id:
            messages.info(request, "You're already on this plan.")
            return redirect('payments:subscription_detail')
            
        # Don't update the plan yet - only store the selected plan ID in session
        request.session['upgrade_plan_id'] = plan_id
        
        # If current subscription has a Stripe subscription ID and is not canceled
        if current_subscription.stripe_subscription_id and current_subscription.status != 'canceled':
            try:
                # For downgrades or between subscription types, always use Stripe
                if plan.price < current_subscription.plan.price or plan.billing_frequency != current_subscription.plan.billing_frequency:
                    # Create checkout session for the new plan
                    checkout_session = create_checkout_session(request, organization, plan, current_subscription)
                    return redirect(checkout_session.url)
                else:
                    # For upgrades within the same billing period, update immediately in Stripe
                    stripe.Subscription.modify(
                        current_subscription.stripe_subscription_id,
                        items=[{
                            'id': stripe.Subscription.retrieve(current_subscription.stripe_subscription_id)['items']['data'][0].id,
                            'price': plan.stripe_price_id,
                        }],
                        proration_behavior='always_invoice',
                    )
                    
                    # On immediate success with Stripe, update the local subscription
                    current_subscription.plan = plan
                    current_subscription.save()
                    
                    messages.success(request, f"Your subscription has been upgraded to {plan.name}.")
                    return redirect('payments:subscription_detail')
            except Exception as e:
                messages.error(request, f"Error upgrading subscription: {str(e)}")
                return render(request, 'payments/upgrade_subscription.html', {
                    'plans': sorted_plans,
                    'current_subscription': current_subscription
                })
        else:
            # For new subscriptions, create Stripe Checkout Session
            try:
                checkout_session = create_checkout_session(request, organization, plan, current_subscription)
                return redirect(checkout_session.url)
            except Exception as e:
                messages.error(request, f"Error creating checkout session: {str(e)}")
                return render(request, 'payments/upgrade_subscription.html', {
                    'plans': sorted_plans,
                    'current_subscription': current_subscription
                })
    
    return render(request, 'payments/upgrade_subscription.html', {
        'plans': sorted_plans,
        'current_subscription': current_subscription
    })

@login_required
def complete_payment(request):
    """Complete an incomplete subscription payment"""
    if request.method != 'POST':
        return redirect('payments:subscription_detail')
    
    subscription_id = request.POST.get('subscription_id')
    subscription = get_object_or_404(Subscription, id=subscription_id, organization=request.user.organization)
    
    # Create a new checkout session for the current plan
    try:
        checkout_session = create_checkout_session(request, request.user.organization, subscription.plan, subscription)
        return redirect(checkout_session.url)
    except Exception as e:
        messages.error(request, f"Error creating checkout session: {str(e)}")
        return redirect('payments:subscription_detail')
    
@login_required
def escrow_payment_instructions(request, payment_id):
    """Show payment instructions for enterprise"""
    payment = get_object_or_404(EscrowPayment, id=payment_id)
    
    # Security check - only the enterprise can see this
    if request.user.organization != payment.pilot_bid.pilot.organization:
        messages.error(request, "You don't have permission to view these payment instructions")
        return redirect('organizations:dashboard')
    
    return render(request, 'payments/escrow_payment_instructions.html', {
        'payment': payment
    })

@login_required
def escrow_payment_confirmation(request, payment_id):
    """Enterprise confirms payment has been sent"""
    payment = get_object_or_404(EscrowPayment, id=payment_id)
    
    # Security check - only the enterprise can confirm payment
    if request.user.organization != payment.pilot_bid.pilot.organization:
        messages.error(request, "You don't have permission to confirm this payment")
        return redirect('organizations:dashboard')
    
    if request.method == 'POST':
        wire_date = request.POST.get('wire_date')
        confirmation = request.POST.get('confirmation')
        
        # Validate date
        try:
            wire_date = datetime.strptime(wire_date, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, "Invalid date format")
            return render(request, 'payments/escrow_payment_confirmation.html', {'payment': payment})
        
        # Mark payment as initiated
        payment.mark_as_payment_initiated(wire_date=wire_date, confirmation=confirmation)
        
        messages.success(request, "Payment confirmation received. Thank you!")
        return redirect('pilots:bid_detail', pk=payment.pilot_bid.id)
    
    return render(request, 'payments/escrow_payment_confirmation.html', {
        'payment': payment
    })

# =============================================================================
# ADMIN VIEWS - Enhanced Workflow Management
# =============================================================================

@login_required
@staff_member_required
def admin_payment_dashboard(request):
    """Enhanced admin dashboard with comprehensive workflow management"""
    
    # 1. Approved bids needing invoice generation (New Stage 1)
    approved_bids_needing_invoice = PilotBid.objects.filter(
        status='approved'
    ).exclude(
        escrow_payment__status='instructions_sent'  # Exclude bids with invoices already sent
    ).select_related(
        'pilot__organization',
        'startup'
    ).prefetch_related(
        'escrow_payment'
    ).order_by('-updated_at')
    
    # 2. Invoices sent, awaiting payment initiation (New Stage 2)
    invoices_sent_awaiting_payment = EscrowPayment.objects.filter(
        status='instructions_sent'
    ).select_related(
        'pilot_bid__pilot__organization',
        'pilot_bid__startup'
    ).order_by('-instructions_sent_at')
    
    # 3. Payments initiated by enterprise, needing verification (Stage 3)
    needs_verification = EscrowPayment.objects.filter(
        status='payment_initiated'
    ).select_related(
        'pilot_bid__pilot__organization',
        'pilot_bid__startup'
    ).order_by('-payment_initiated_at')
    
    # 4. Payments received, ready to activate pilot work (Stage 4)
    payment_received_ready_to_activate = EscrowPayment.objects.filter(
        status='received', 
        pilot_bid__status='approved'
    ).select_related(
        'pilot_bid__pilot__organization',
        'pilot_bid__startup'
    ).order_by('-received_at')
    
    # 5. Work completed, ready for payment release (Stage 5)
    completed_ready_for_release = EscrowPayment.objects.filter(
        status='received', 
        pilot_bid__status='completed'
    ).select_related(
        'pilot_bid__pilot__organization',
        'pilot_bid__startup'
    ).order_by('-received_at')
    
    # 6. Recent activity logs
    recent_logs = EscrowPaymentLog.objects.select_related(
        'escrow_payment__pilot_bid__pilot',
        'changed_by'
    ).order_by('-created_at')[:10]
    
    # Calculate stats for the dashboard
    total_escrow_amount = EscrowPayment.objects.filter(
        status__in=['received', 'payment_initiated', 'instructions_sent']
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    context = {
        # New workflow stages
        'approved_bids_needing_invoice': approved_bids_needing_invoice[:5],
        'invoices_sent_awaiting_payment': invoices_sent_awaiting_payment[:5],
        'needs_verification': needs_verification[:5],
        'payment_received_ready_to_activate': payment_received_ready_to_activate[:5],
        'completed_ready_for_release': completed_ready_for_release[:5],
        'recent_logs': recent_logs,
        'total_escrow_amount': total_escrow_amount,
        
        # Dashboard stats
        'invoice_generation_count': approved_bids_needing_invoice.count(),
        'invoiced_awaiting_payment_count': invoices_sent_awaiting_payment.count(),
        'verification_count': needs_verification.count(),
        'activation_count': payment_received_ready_to_activate.count(),
        'release_count': completed_ready_for_release.count(),
    }
    
    return render(request, 'admin/payments/admin_payment_dashboard.html', context)

@login_required
@staff_member_required
def admin_mark_invoice_sent(request, bid_id):
    """Admin marks invoice as sent for an approved bid"""
    if request.method != 'POST':
        return redirect('payments:admin_payment_dashboard')
    
    bid = get_object_or_404(PilotBid, id=bid_id)
    
    # Validate bid status
    if bid.status != 'approved':
        messages.error(request, f"Bid must be in 'approval_pending' status. Current status: {bid.get_status_display()}")
        return redirect('payments:admin_payment_dashboard')
    
    # Get or create escrow payment
    try:
        escrow_payment = bid.escrow_payment
        if escrow_payment.status != 'pending':
            messages.error(request, f"Payment must be in 'pending' status. Current status: {escrow_payment.get_status_display()}")
            return redirect('payments:admin_payment_dashboard')
    except EscrowPayment.DoesNotExist:
        messages.error(request, "No escrow payment found for this bid")
        return redirect('payments:admin_payment_dashboard')
    
    # Get admin notes
    notes = request.POST.get('notes', '')
    
    # Create log entry
    EscrowPaymentLog.objects.create(
        escrow_payment=escrow_payment,
        previous_status=escrow_payment.status,
        new_status='instructions_sent',
        changed_by=request.user,
        notes=f"Invoice sent to enterprise. {notes}".strip()
    )
    
    # Mark invoice as sent
    escrow_payment.status = 'instructions_sent'
    escrow_payment.instructions_sent_at = timezone.now()
    escrow_payment.save()
    
    # Create notifications for enterprise
    for user in bid.pilot.organization.users.all():
        create_notification(
            recipient=user,
            notification_type='payment_invoice_sent',
            title=f"Invoice Ready: {bid.pilot.title}",
            message=f"Your invoice for '{bid.pilot.title}' is ready. Please review payment instructions and initiate wire transfer.",
            related_pilot=bid.pilot,
            related_bid=bid
        )
    
    messages.success(request, f"Invoice marked as sent for bid on '{bid.pilot.title}'")
    return redirect('payments:admin_payment_dashboard')

@login_required
@staff_member_required
def admin_activate_pilot_work(request, payment_id):
    """Admin activates pilot work after payment verification"""
    if request.method != 'POST':
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    payment = get_object_or_404(EscrowPayment, id=payment_id)
    
    # Verify that payment is in 'received' status
    if payment.status != 'received':
        messages.error(request, f"Payment must be in 'received' status. Current status: {payment.get_status_display()}")
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    # Verify that bid is in approved status
    if payment.pilot_bid.status != 'approved':
        if payment.pilot_bid.status == 'live':
            messages.warning(request, "This pilot has already been activated")
        else:
            messages.error(request, f"Pilot bid is in '{payment.pilot_bid.get_status_display()}' status and cannot be activated")
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    # Mark the bid as live
    try:
        success = payment.pilot_bid.mark_as_live()
        
        if success:
            # Create log entry
            EscrowPaymentLog.objects.create(
                escrow_payment=payment,
                previous_status=payment.status,
                new_status=payment.status,  # Status doesn't change for payment
                changed_by=request.user,
                notes="Pilot work activated by admin - bid marked as live"
            )
            
            # Create notifications for both parties
            # Notify enterprise
            for user in payment.pilot_bid.pilot.organization.users.all():
                create_notification(
                    recipient=user,
                    notification_type='pilot_activated',
                    title=f"Work Started: {payment.pilot_bid.pilot.title}",
                    message=f"Payment verified! Work on '{payment.pilot_bid.pilot.title}' has been activated. {payment.pilot_bid.startup.name} can now begin work.",
                    related_pilot=payment.pilot_bid.pilot,
                    related_bid=payment.pilot_bid
                )
            
            # Notify startup
            for user in payment.pilot_bid.startup.users.all():
                create_notification(
                    recipient=user,
                    notification_type='pilot_activated',
                    title=f"Work Activated: {payment.pilot_bid.pilot.title}",
                    message=f"Great news! Payment has been verified and your pilot '{payment.pilot_bid.pilot.title}' is now live. You can begin work immediately.",
                    related_pilot=payment.pilot_bid.pilot,
                    related_bid=payment.pilot_bid
                )
            
            messages.success(request, f"Pilot work activated for '{payment.pilot_bid.pilot.title}'")
        else:
            messages.error(request, "Error activating pilot work: status transition failed")
    except Exception as e:
        messages.error(request, f"Error activating pilot work: {str(e)}")
    
    return redirect('payments:admin_payment_dashboard')

@login_required
@staff_member_required
def admin_release_startup_payment(request, payment_id):
    """Admin releases payment to startup after work completion"""
    if request.method != 'POST':
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    payment = get_object_or_404(EscrowPayment, id=payment_id)
    
    # Enhanced validation
    if payment.status != 'received':
        messages.error(request, f"Payment must be in 'received' status. Current status: {payment.get_status_display()}")
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    if payment.pilot_bid.status != 'completed':
        messages.error(request, "The pilot must be marked as completed by the enterprise before releasing payment")
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    # Get admin notes
    notes = request.POST.get('notes', '')
    
    # Create log entry
    EscrowPaymentLog.objects.create(
        escrow_payment=payment,
        previous_status=payment.status,
        new_status='released',
        changed_by=request.user,
        notes=f"Payment released to startup. {notes}".strip()
    )
    
    # Mark payment as released
    payment.mark_as_released()
    
    # Create comprehensive notifications
    # Notify startup about payment release
    for user in payment.pilot_bid.startup.users.all():
        create_notification(
            recipient=user,
            notification_type='payment_released',
            title=f"Payment Released: {payment.pilot_bid.pilot.title}",
            message=f"Congratulations! Payment of ${payment.startup_amount} for '{payment.pilot_bid.pilot.title}' has been released to your account.",
            related_pilot=payment.pilot_bid.pilot,
            related_bid=payment.pilot_bid
        )
    
    # Notify enterprise about completion
    for user in payment.pilot_bid.pilot.organization.users.all():
        create_notification(
            recipient=user,
            notification_type='pilot_payment_completed',
            title=f"Pilot Completed: {payment.pilot_bid.pilot.title}",
            message=f"Payment for '{payment.pilot_bid.pilot.title}' has been successfully released to {payment.pilot_bid.startup.name}. Your pilot is now complete!",
            related_pilot=payment.pilot_bid.pilot,
            related_bid=payment.pilot_bid
        )
    
    messages.success(request, f"Payment of ${payment.startup_amount} released to {payment.pilot_bid.startup.name}")
    return redirect('payments:admin_payment_dashboard')

@login_required
@staff_member_required
def admin_escrow_payments(request):
    """Enhanced admin view for all escrow payments with 5-stage workflow filtering"""
    tab = request.GET.get('tab', 'all')
    search = request.GET.get('search', '')
    amount_filter = request.GET.get('amount_filter', '')
    
    # Base queryset with optimized select_related
    payments = EscrowPayment.objects.select_related(
        'pilot_bid__pilot__organization',
        'pilot_bid__startup'
    ).prefetch_related(
        'pilot_bid__pilot'
    )
    
    # Apply tab filters based on new 5-stage workflow
    if tab == 'invoice_pending':
        payments = payments.filter(status='pending')
    elif tab == 'invoice_sent':
        payments = payments.filter(status='instructions_sent')
    elif tab == 'verification':
        payments = payments.filter(status='payment_initiated')
    elif tab == 'ready_for_release':
        payments = payments.filter(status='received', pilot_bid__status='completed')
    elif tab == 'completed':
        payments = payments.filter(status='released')
    elif tab == 'activation':
        payments = payments.filter(status='received', pilot_bid__status='approved')
    # 'all' tab shows everything (no additional filter)
    
    # Apply search filter
    if search:
        payments = payments.filter(
            Q(reference_code__icontains=search) | 
            Q(pilot_bid__pilot__title__icontains=search) |
            Q(pilot_bid__pilot__organization__name__icontains=search) |
            Q(pilot_bid__startup__name__icontains=search)
        )
    
    # Apply amount filter
    if amount_filter == 'small':
        payments = payments.filter(total_amount__lt=1000)
    elif amount_filter == 'medium':
        payments = payments.filter(total_amount__gte=1000, total_amount__lte=10000)
    elif amount_filter == 'large':
        payments = payments.filter(total_amount__gt=10000)
    
    # Order by most recent activity
    payments = payments.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(payments, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get counts for tabs (matching 5-stage workflow)
    invoice_pending_count = EscrowPayment.objects.filter(status='pending').count()
    invoice_sent_count = EscrowPayment.objects.filter(status='instructions_sent').count()
    verification_count = EscrowPayment.objects.filter(status='payment_initiated').count()
    activation_count = EscrowPayment.objects.filter(status='received', pilot_bid__status='approved').count()
    ready_for_release_count = EscrowPayment.objects.filter(status='received', pilot_bid__status='completed').count()
    completed_count = EscrowPayment.objects.filter(status='released').count()
    all_count = EscrowPayment.objects.count()
    
    context = {
        'payments': page_obj,
        'tab': tab,
        'search': search,
        'amount_filter': amount_filter,
        # Updated tab counts for 5-stage workflow
        'invoice_pending_count': invoice_pending_count,
        'invoice_sent_count': invoice_sent_count,
        'verification_count': verification_count,
        'activation_count': activation_count,
        'ready_for_release_count': ready_for_release_count,
        'completed_count': completed_count,
        'all_count': all_count,
    }
    
    return render(request, 'admin/payments/admin_escrow_payments.html', context)

@login_required
@staff_member_required
def admin_escrow_payment_detail(request, payment_id):
    """Enhanced admin view for individual payment details"""
    payment = get_object_or_404(
        EscrowPayment.objects.select_related(
            'pilot_bid__pilot__organization',
            'pilot_bid__startup'
        ), 
        id=payment_id
    )
    
    # Get payment logs for audit trail
    payment_logs = EscrowPaymentLog.objects.filter(
        escrow_payment=payment
    ).select_related('changed_by').order_by('-created_at')
    
    context = {
        'payment': payment,
        'payment_logs': payment_logs,
    }
    
    return render(request, 'admin/payments/admin_escrow_payment_detail.html', context)

@login_required
@staff_member_required
def admin_mark_payment_received(request, payment_id):
    """Admin marks payment as received with enhanced workflow"""
    if request.method != 'POST':
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    payment = get_object_or_404(EscrowPayment, id=payment_id)
    
    # Validate status transition
    if payment.status != 'payment_initiated':
        messages.error(request, f"Payment must be in 'payment_initiated' status to mark as received. Current status: {payment.get_status_display()}")
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    # Get admin notes
    notes = request.POST.get('notes', '')
    
    # Create log entry
    EscrowPaymentLog.objects.create(
        escrow_payment=payment,
        previous_status=payment.status,
        new_status='received',
        changed_by=request.user,
        notes=notes
    )
    
    # Mark payment as received
    payment.mark_as_received()
    
    # Create notifications
    # Notify enterprise
    for user in payment.pilot_bid.pilot.organization.users.all():
        create_notification(
            recipient=user,
            notification_type='payment_verified',
            title=f"Payment Verified: {payment.pilot_bid.pilot.title}",
            message=f"Your payment for '{payment.pilot_bid.pilot.title}' has been verified. The pilot will be activated soon.",
            related_pilot=payment.pilot_bid.pilot,
            related_bid=payment.pilot_bid
        )
    
    # Notify startup
    for user in payment.pilot_bid.startup.users.all():
        create_notification(
            recipient=user,
            notification_type='payment_verified',
            title=f"Payment Verified: {payment.pilot_bid.pilot.title}",
            message=f"Payment for '{payment.pilot_bid.pilot.title}' has been verified. Work will be activated soon.",
            related_pilot=payment.pilot_bid.pilot,
            related_bid=payment.pilot_bid
        )
    
    messages.success(request, f"Payment {payment.reference_code} marked as received and verified")
    return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)

@login_required
@staff_member_required
def admin_release_payment(request, payment_id):
    """Admin releases payment to startup with enhanced validation"""
    if request.method != 'POST':
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    payment = get_object_or_404(EscrowPayment, id=payment_id)
    
    # Enhanced validation
    if payment.status != 'received':
        messages.error(request, f"Payment must be in 'received' status to be released. Current status: {payment.get_status_display()}")
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    if payment.pilot_bid.status != 'completed':
        messages.error(request, "The pilot must be marked as completed by the enterprise before releasing payment")
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    # Get admin notes
    notes = request.POST.get('notes', '')
    
    # Create log entry
    EscrowPaymentLog.objects.create(
        escrow_payment=payment,
        previous_status=payment.status,
        new_status='released',
        changed_by=request.user,
        notes=notes
    )
    
    # Mark payment as released
    payment.mark_as_released()
    
    # Create comprehensive notifications
    # Notify startup about payment release
    for user in payment.pilot_bid.startup.users.all():
        create_notification(
            recipient=user,
            notification_type='payment_released',
            title=f"Payment Released: {payment.pilot_bid.pilot.title}",
            message=f"Congratulations! Payment of ${payment.startup_amount} for '{payment.pilot_bid.pilot.title}' has been released to your account.",
            related_pilot=payment.pilot_bid.pilot,
            related_bid=payment.pilot_bid
        )
    
    # Notify enterprise about completion
    for user in payment.pilot_bid.pilot.organization.users.all():
        create_notification(
            recipient=user,
            notification_type='pilot_payment_completed',
            title=f"Pilot Payment Completed: {payment.pilot_bid.pilot.title}",
            message=f"Payment for '{payment.pilot_bid.pilot.title}' has been successfully released to {payment.pilot_bid.startup.name}.",
            related_pilot=payment.pilot_bid.pilot,
            related_bid=payment.pilot_bid
        )
    
    messages.success(request, f"Payment {payment.reference_code} released to {payment.pilot_bid.startup.name}")
    return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)

@login_required
@staff_member_required
def admin_kickoff_pilot(request, payment_id):
    """Admin kicks off a pilot after payment verification - NEW WORKFLOW"""
    if request.method != 'POST':
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    payment = get_object_or_404(EscrowPayment, id=payment_id)
    
    # Verify that payment is in 'received' status
    if payment.status != 'received':
        messages.error(request, f"Payment must be in 'received' status to kick off the pilot. Current status: {payment.get_status_display()}")
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    # Verify that bid is in approved status
    if payment.pilot_bid.status != 'approved':
        if payment.pilot_bid.status == 'live':
            messages.warning(request, "This pilot has already been kicked off")
        else:
            messages.error(request, f"Pilot is in '{payment.pilot_bid.get_status_display()}' status and cannot be kicked off")
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    # Mark the bid as live
    try:
        success = payment.pilot_bid.mark_as_live()
        
        if success:
            # Create log entry
            EscrowPaymentLog.objects.create(
                escrow_payment=payment,
                previous_status=payment.status,
                new_status=payment.status,  # Status doesn't change
                changed_by=request.user,
                notes="Pilot kicked off by admin - bid marked as live"
            )
            
            # Create notifications for both parties
            # Notify enterprise
            for user in payment.pilot_bid.pilot.organization.users.all():
                create_notification(
                    recipient=user,
                    notification_type='pilot_activated',
                    title=f"Pilot Activated: {payment.pilot_bid.pilot.title}",
                    message=f"Your pilot '{payment.pilot_bid.pilot.title}' has been activated. {payment.pilot_bid.startup.name} can now begin work.",
                    related_pilot=payment.pilot_bid.pilot,
                    related_bid=payment.pilot_bid
                )
            
            # Notify startup
            for user in payment.pilot_bid.startup.users.all():
                create_notification(
                    recipient=user,
                    notification_type='pilot_activated',
                    title=f"Pilot Activated: {payment.pilot_bid.pilot.title}",
                    message=f"Great news! Payment has been verified and your pilot '{payment.pilot_bid.pilot.title}' is now live. You can begin work immediately.",
                    related_pilot=payment.pilot_bid.pilot,
                    related_bid=payment.pilot_bid
                )
            
            messages.success(request, f"Pilot '{payment.pilot_bid.pilot.title}' has been activated successfully")
        else:
            messages.error(request, "Error activating pilot: status transition failed")
    except Exception as e:
        messages.error(request, f"Error activating pilot: {str(e)}")
    
    return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)

@login_required
@staff_member_required
def admin_export_payments_csv(request):
    """Export payments as CSV with current filters applied"""
    # Apply same filters as admin_escrow_payments
    tab = request.GET.get('tab')
    search = request.GET.get('search')
    amount_filter = request.GET.get('amount_filter')
    
    # Base queryset
    payments = EscrowPayment.objects.select_related(
        'pilot_bid__pilot__organization',
        'pilot_bid__startup'
    )
    
    # Apply filters (same logic as list view)
    if tab == 'initiated':
        payments = payments.filter(status='payment_initiated')
    elif tab == 'ready':
        payments = payments.filter(status='received', pilot_bid__status='completed')
    elif tab == 'completed':
        payments = payments.filter(status='released')
    
    if search:
        payments = payments.filter(
            Q(reference_code__icontains=search) | 
            Q(pilot_bid__pilot__title__icontains=search) |
            Q(pilot_bid__pilot__organization__name__icontains=search) |
            Q(pilot_bid__startup__name__icontains=search)
        )
    
    if amount_filter == 'small':
        payments = payments.filter(total_amount__lt=1000)
    elif amount_filter == 'medium':
        payments = payments.filter(total_amount__gte=1000, total_amount__lte=10000)
    elif amount_filter == 'large':
        payments = payments.filter(total_amount__gt=10000)
    
    # Order by most recent activity
    payments = payments.order_by('-created_at')
    
    # Create the HttpResponse with CSV header
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="escrow_payments_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Reference Code', 'Pilot Title', 'Enterprise', 'Startup', 
        'Total Amount', 'Startup Amount', 'Platform Fee', 'Status', 
        'Created Date', 'Payment Initiated', 'Received Date', 'Released Date'
    ])
    
    for payment in payments:
        writer.writerow([
            payment.reference_code,
            payment.pilot_bid.pilot.title,
            payment.pilot_bid.pilot.organization.name,
            payment.pilot_bid.startup.name,
            payment.total_amount,
            payment.startup_amount,
            payment.platform_fee,
            payment.get_status_display(),
            payment.created_at.strftime('%Y-%m-%d %H:%M'),
            payment.payment_initiated_at.strftime('%Y-%m-%d %H:%M') if payment.payment_initiated_at else '',
            payment.received_at.strftime('%Y-%m-%d %H:%M') if payment.received_at else '',
            payment.released_at.strftime('%Y-%m-%d %H:%M') if payment.released_at else ''
        ])
    
    return response