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
from django.db.models import Q, Sum, Count, F
from django.core.paginator import Paginator
import csv
from apps.notifications.services import create_notification

from .models import PricingPlan, Subscription, Payment, PaymentHoldingService, PaymentHoldingServiceLog, FreeAccountCode
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
        free_account_code = request.POST.get('free_account_code')
        
        # Debug logging
        print(f"POST data - plan_id: {plan_id}, free_account_code: {free_account_code}")
        
        # Handle free account code
        if plan_id == 'free_account' and free_account_code:
            try:
                code = FreeAccountCode.objects.get(code=free_account_code)
                if code.can_be_used():
                    # Use the plan specified by the code
                    plan = code.plan
                    
                    # Validate that org type matches plan type
                    plan_org_type = 'startup' if 'startup' in plan.plan_type else 'enterprise'
                    if organization.type != plan_org_type:
                        messages.error(request, f"This code is for {plan_org_type} organizations only")
                        return render(request, 'payments/plan_selection.html', {
                            'plans': sorted_plans,
                            'organization': organization
                        })
                    
                    # Create or update subscription with free account code
                    subscription, created = Subscription.objects.get_or_create(
                        organization=organization,
                        defaults={
                            'plan': plan,
                            'status': 'active',
                            'free_account_code': code,
                            'current_period_start': timezone.now(),
                            'current_period_end': code.get_subscription_end_date(),
                            'stripe_customer_id': '',
                            'stripe_subscription_id': '',
                        }
                    )
                    
                    if not created:
                        subscription.plan = plan
                        subscription.status = 'active'
                        subscription.free_account_code = code
                        subscription.current_period_start = timezone.now()
                        subscription.current_period_end = code.get_subscription_end_date()
                        subscription.stripe_customer_id = ''
                        subscription.stripe_subscription_id = ''
                        subscription.save()
                    
                    # Mark code as used
                    code.use_code()
                    
                    # Mark organization as onboarded (subscription active)
                    # but keep has_payment_method=False since no card on file
                    organization.onboarding_completed = True
                    organization.save()
                    
                    messages.success(request, f"Free {plan.name} account activated for {code.free_months} months!")
                    return redirect('organizations:dashboard')
                else:
                    messages.error(request, "Invalid or expired free account code")
            except FreeAccountCode.DoesNotExist:
                messages.error(request, "Invalid free account code")
        
        # Handle regular plan selection
        elif plan_id and plan_id != 'free_account':
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
        elif plan_id == 'free_account' and not free_account_code:
            # User selected free account but didn't provide a code
            messages.error(request, "Please enter your free account code")
            return render(request, 'payments/plan_selection.html', {
                'plans': sorted_plans,
                'organization': organization
            })
        else:
            # No plan selected at all
            messages.error(request, "Please select a plan or enter a valid free account code")
            return render(request, 'payments/plan_selection.html', {
                'plans': sorted_plans,
                'organization': organization
            })
    
    return render(request, 'payments/plan_selection.html', {
        'plans': sorted_plans,
        'organization': organization
    })

@login_required
@csrf_exempt
def validate_free_code(request):
    """AJAX endpoint to validate free account codes"""
    if request.method != 'POST':
        return JsonResponse({'valid': False, 'message': 'Invalid request method'})
    
    try:
        data = json.loads(request.body)
        code = data.get('code', '').strip()
        
        if not code:
            return JsonResponse({'valid': False, 'message': 'Please enter a code'})
        
        try:
            free_code = FreeAccountCode.objects.select_related('plan').get(code=code)
            if free_code.can_be_used():
                # Get the user's organization
                organization = getattr(request.user, 'organization', None)
                if not organization:
                    return JsonResponse({'valid': False, 'message': 'Organization not found'})
                
                # Validate that org type matches plan type
                plan_org_type = 'startup' if 'startup' in free_code.plan.plan_type else 'enterprise'
                if organization.type != plan_org_type:
                    return JsonResponse({'valid': False, 'message': f'This code is for {plan_org_type} organizations only'})
                
                # Store the code in session for later use
                request.session['validated_free_code'] = code
                return JsonResponse({
                    'valid': True, 
                    'message': '',  # Remove the redundant message - we'll only show the green bubble
                    'plan_name': free_code.plan.name,
                    'plan_price': str(free_code.plan.price),
                    'plan_billing': free_code.plan.billing_frequency,
                    'free_months': free_code.free_months
                })
            else:
                return JsonResponse({'valid': False, 'message': 'Code is expired or has reached usage limit'})
        except FreeAccountCode.DoesNotExist:
            return JsonResponse({'valid': False, 'message': 'Invalid code'})
    
    except json.JSONDecodeError:
        return JsonResponse({'valid': False, 'message': 'Invalid request data'})
    except Exception as e:
        return JsonResponse({'valid': False, 'message': 'Error validating code'})

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
def payment_holding_instructions(request, payment_id):
    """Show payment instructions for enterprise"""
    payment = get_object_or_404(PaymentHoldingService, id=payment_id)
    
    # Security check - only the enterprise can see this
    if request.user.organization != payment.pilot_bid.pilot.organization:
        messages.error(request, "You don't have permission to view these payment instructions")
        return redirect('organizations:dashboard')
    
    return render(request, 'payments/payment_holding_instructions.html', {
        'payment': payment
    })

@login_required
def payment_holding_confirmation(request, payment_id):
    """Enterprise confirms payment has been sent"""
    payment = get_object_or_404(PaymentHoldingService, id=payment_id)
    
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
            return render(request, 'payments/payment_holding_confirmation.html', {'payment': payment})
        
        # Mark payment as initiated (legacy support - no longer used in 4-stage workflow)
        payment.mark_as_payment_initiated(wire_date=wire_date, confirmation=confirmation)
        
        messages.success(request, "Payment confirmation received. Thank you!")
        return redirect('pilots:bid_detail', pk=payment.pilot_bid.id)
    
    return render(request, 'payments/payment_holding_confirmation.html', {
        'payment': payment
    })

# =============================================================================
# ADMIN VIEWS - Updated for 4-Stage Workflow
# =============================================================================

@login_required
@staff_member_required
def admin_payment_dashboard(request):
    """Enhanced admin dashboard with 4-stage workflow management"""
    
    # STAGE 1: Approved bids needing invoice generation
    approved_bids_needing_invoice = PilotBid.objects.filter(
        status='approved'
    ).exclude(
        payment_holding_service__status='instructions_sent'  # Exclude bids with invoices already sent
    ).select_related(
        'pilot__organization',
        'startup'
    ).prefetch_related(
        'payment_holding_service'
    ).order_by('-updated_at')
    
    # STAGE 2: Invoices sent, awaiting payment
    invoices_sent_awaiting_payment = PaymentHoldingService.objects.filter(
        status='instructions_sent'
    ).select_related(
        'pilot_bid__pilot__organization',
        'pilot_bid__startup'
    ).order_by('-instructions_sent_at')
    
    # STAGE 3: Payments ready to confirm and activate (combined verification + activation)
    ready_to_confirm_and_activate = PaymentHoldingService.objects.filter(
        status='instructions_sent'  # Payments awaiting admin confirmation
    ).select_related(
        'pilot_bid__pilot__organization',
        'pilot_bid__startup'
    ).order_by('-instructions_sent_at')
    
    # STAGE 4: Work completed, ready for payment release
    completed_ready_for_release = PaymentHoldingService.objects.filter(
        status='received', 
        pilot_bid__status='completed'
    ).select_related(
        'pilot_bid__pilot__organization',
        'pilot_bid__startup'
    ).order_by('-received_at')

    # Active work sections
    active_pilots = PilotBid.objects.filter(
        status='live'
    ).select_related(
        'pilot__organization',
        'startup',
        'payment_holding_service'
    ).prefetch_related(
        'pilot'
    ).order_by('-updated_at')
    
    # Payment confirmed but work not yet marked as live
    payment_confirmed_ready_to_start = PaymentHoldingService.objects.filter(
        status='received',
        pilot_bid__status='approved'  # Payment confirmed but work not yet marked as live
    ).select_related(
        'pilot_bid__pilot__organization',
        'pilot_bid__startup'
    ).order_by('-received_at')
    
    # Recent activity logs
    recent_logs = PaymentHoldingServiceLog.objects.select_related(
        'payment_holding_service__pilot_bid__pilot',
        'changed_by'
    ).order_by('-created_at')[:10]
    
    # Calculate stats for the dashboard
    total_payment_holding_amount = PaymentHoldingService.objects.filter(
        status__in=['received', 'instructions_sent']
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Free Account Codes stats
    from .models import FreeAccountCode
    active_codes = FreeAccountCode.objects.filter(is_active=True, valid_until__gt=timezone.now())
    total_codes_count = FreeAccountCode.objects.count()
    active_codes_count = active_codes.count()
    codes_used_today = FreeAccountCode.objects.filter(
        subscription__created_at__date=timezone.now().date()
    ).count()
    recent_codes = FreeAccountCode.objects.order_by('-created_at')[:5]
    
    context = {
        # 4-stage workflow
        'approved_bids_needing_invoice': approved_bids_needing_invoice[:5],
        'invoices_sent_awaiting_payment': invoices_sent_awaiting_payment[:5],
        'ready_to_confirm_and_activate': ready_to_confirm_and_activate[:5],
        'completed_ready_for_release': completed_ready_for_release[:5],
        'recent_logs': recent_logs,
        'total_payment_holding_amount': total_payment_holding_amount,
        
        # NEW: Active work sections
        'active_pilots': active_pilots[:8],  # Show up to 8 active pilots
        'payment_confirmed_ready_to_start': payment_confirmed_ready_to_start[:5],
        
        # Dashboard stats
        'invoice_generation_count': approved_bids_needing_invoice.count(),
        'invoiced_awaiting_payment_count': invoices_sent_awaiting_payment.count(),
        'confirm_and_activate_count': ready_to_confirm_and_activate.count(),
        'release_count': completed_ready_for_release.count(),
        
        # NEW: Active work stats
        'active_pilots_count': active_pilots.count(),
        'payment_confirmed_count': payment_confirmed_ready_to_start.count(),
        
        # Free Account Codes stats
        'total_codes_count': total_codes_count,
        'active_codes_count': active_codes_count,
        'codes_used_today': codes_used_today,
        'recent_codes': recent_codes,
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
        messages.error(request, f"Bid must be in 'approved' status. Current status: {bid.get_status_display()}")
        return redirect('payments:admin_payment_dashboard')
    
    # Get or create payment holding service
    try:
        payment_holding_service = bid.payment_holding_service
        if payment_holding_service.status != 'pending':
            messages.error(request, f"Payment must be in 'pending' status. Current status: {payment_holding_service.get_status_display()}")
            return redirect('payments:admin_payment_dashboard')
    except PaymentHoldingService.DoesNotExist:
        messages.error(request, "No payment holding service found for this bid")
        return redirect('payments:admin_payment_dashboard')
    
    # Get admin notes
    notes = request.POST.get('notes', '')
    
    # Create log entry
    PaymentHoldingServiceLog.objects.create(
        payment_holding_service=payment_holding_service,
        previous_status=payment_holding_service.status,
        new_status='instructions_sent',
        changed_by=request.user,
        notes=f"Invoice sent to enterprise. {notes}".strip()
    )
    
    # Mark invoice as sent
    payment_holding_service.status = 'instructions_sent'
    payment_holding_service.instructions_sent_at = timezone.now()
    payment_holding_service.save()
    
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
def admin_confirm_payment_and_activate(request, payment_id):
    """Admin confirms payment received AND activates work in one step"""
    if request.method != 'POST':
        return redirect('payments:admin_payment_holding_detail', payment_id=payment_id)
    
    payment = get_object_or_404(PaymentHoldingService, id=payment_id)
    
    # Verify that payment is in 'instructions_sent' status
    if payment.status != 'instructions_sent':
        messages.error(request, f"Payment must be in 'instructions_sent' status. Current status: {payment.get_status_display()}")
        return redirect('payments:admin_payment_holding_detail', payment_id=payment_id)
    
    # Get admin notes
    notes = request.POST.get('notes', '')
    
    try:
        # Mark payment as received and activate work
        payment.mark_as_received_and_activate(user=request.user, notes=notes)
        messages.success(request, f"Payment confirmed and work activated for '{payment.pilot_bid.pilot.title}'")
    except Exception as e:
        messages.error(request, f"Error confirming payment and activating work: {str(e)}")
        return redirect('payments:admin_payment_holding_detail', payment_id=payment_id)
    
    return redirect('payments:admin_payment_dashboard')

@login_required
@staff_member_required
def admin_release_startup_payment(request, payment_id):
    """Admin releases payment to startup after work completion"""
    if request.method != 'POST':
        return redirect('payments:admin_payment_holding_detail', payment_id=payment_id)
    
    payment = get_object_or_404(PaymentHoldingService, id=payment_id)
    
    # Enhanced validation
    if payment.status != 'received':
        messages.error(request, f"Payment must be in 'received' status. Current status: {payment.get_status_display()}")
        return redirect('payments:admin_payment_holding_detail', payment_id=payment_id)
    
    if payment.pilot_bid.status != 'completed':
        messages.error(request, "The pilot must be marked as completed by the enterprise before releasing payment")
        return redirect('payments:admin_payment_holding_detail', payment_id=payment_id)
    
    # Get admin notes
    notes = request.POST.get('notes', '')
    
    # Mark payment as released
    success = payment.mark_as_released(user=request.user, notes=notes)
    
    if success:
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
    else:
        messages.error(request, "Error releasing payment")
    
    return redirect('payments:admin_payment_dashboard')

@login_required
@staff_member_required
def admin_payment_holding_services(request):
    """Enhanced admin view for all payment holding services with 4-stage workflow filtering"""
    tab = request.GET.get('tab', 'all')
    search = request.GET.get('search', '')
    amount_filter = request.GET.get('amount_filter', '')
    
    # Base queryset with optimized select_related
    payments = PaymentHoldingService.objects.select_related(
        'pilot_bid__pilot__organization',
        'pilot_bid__startup'
    ).prefetch_related(
        'pilot_bid__pilot'
    )
    
    # Apply tab filters based on new 4-stage workflow
    if tab == 'invoice_pending':
        payments = payments.filter(status='pending')
    elif tab == 'invoice_sent':
        payments = payments.filter(status='instructions_sent')
    elif tab == 'ready_for_release':
        payments = payments.filter(status='received', pilot_bid__status='completed')
    elif tab == 'completed':
        payments = payments.filter(status='released')
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
    
    # Get counts for tabs (4-stage workflow)
    invoice_pending_count = PaymentHoldingService.objects.filter(status='pending').count()
    invoice_sent_count = PaymentHoldingService.objects.filter(status='instructions_sent').count()
    ready_for_release_count = PaymentHoldingService.objects.filter(status='received', pilot_bid__status='completed').count()
    completed_count = PaymentHoldingService.objects.filter(status='released').count()
    all_count = PaymentHoldingService.objects.count()
    
    context = {
        'payments': page_obj,
        'tab': tab,
        'search': search,
        'amount_filter': amount_filter,
        # Updated tab counts for 4-stage workflow
        'invoice_pending_count': invoice_pending_count,
        'invoice_sent_count': invoice_sent_count,
        'ready_for_release_count': ready_for_release_count,
        'completed_count': completed_count,
        'all_count': all_count,
    }
    
    return render(request, 'admin/payments/admin_payment_holding_services.html', context)

@login_required
@staff_member_required
def admin_payment_holding_detail(request, payment_id):
    """Enhanced admin view for individual payment details"""
    payment = get_object_or_404(
        PaymentHoldingService.objects.select_related(
            'pilot_bid__pilot__organization',
            'pilot_bid__startup'
        ), 
        id=payment_id
    )
    
    # Get payment logs for audit trail
    payment_logs = PaymentHoldingServiceLog.objects.filter(
        payment_holding_service=payment
    ).select_related('changed_by').order_by('-created_at')
    
    context = {
        'payment': payment,
        'payment_logs': payment_logs,
    }
    
    return render(request, 'admin/payments/admin_payment_holding_detail.html', context)

@login_required
@staff_member_required
def admin_export_payments_csv(request):
    """Export payments as CSV with current filters applied"""
    # Apply same filters as admin_payment_holding_services
    tab = request.GET.get('tab')
    search = request.GET.get('search')
    amount_filter = request.GET.get('amount_filter')
    
    # Base queryset
    payments = PaymentHoldingService.objects.select_related(
        'pilot_bid__pilot__organization',
        'pilot_bid__startup'
    )
    
    # Apply filters (same logic as list view)
    if tab == 'invoice_pending':
        payments = payments.filter(status='pending')
    elif tab == 'invoice_sent':
        payments = payments.filter(status='instructions_sent')
    elif tab == 'ready_for_release':
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
    response['Content-Disposition'] = f'attachment; filename="payment_holding_services_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Reference Code', 'Pilot Title', 'Pilot ID', 'Enterprise Name', 'Enterprise Contact',
        'Enterprise Email', 'Enterprise Phone', 'Startup Name', 'Startup Contact', 
        'Startup Email', 'Startup Phone', 'Total Amount', 'Startup Amount', 'Platform Fee', 
        'Enterprise Fee %', 'Startup Fee %', 'Payment Status', 'Bid Status', 
        'Payment Reference', 'Admin Notes', 'Created Date', 'Instructions Sent Date', 
        'Payment Initiated Date', 'Received Date', 'Released Date'
    ])
    
    # Prefetch related data for better performance
    payments = payments.prefetch_related(
        'pilot_bid__pilot__organization__users',
        'pilot_bid__startup__users'
    )
    
    for payment in payments:
        # Get enterprise contact info
        enterprise = payment.pilot_bid.pilot.organization
        enterprise_contact = enterprise.primary_contact_name or ''
        enterprise_email = ''
        if enterprise.users.exists():
            enterprise_email = enterprise.users.first().email
        enterprise_phone = enterprise.primary_contact_phone or ''
        
        # Get startup contact info
        startup = payment.pilot_bid.startup
        startup_contact = startup.primary_contact_name or ''
        startup_email = ''
        if startup.users.exists():
            startup_email = startup.users.first().email
        startup_phone = startup.primary_contact_phone or ''
        
        writer.writerow([
            payment.reference_code,
            payment.pilot_bid.pilot.title,
            payment.pilot_bid.pilot.id,
            enterprise.name,
            enterprise_contact,
            enterprise_email,
            enterprise_phone,
            startup.name,
            startup_contact,
            startup_email,
            startup_phone,
            payment.total_amount,
            payment.startup_amount,
            payment.platform_fee,
            payment.enterprise_fee_percentage,
            payment.startup_fee_percentage,
            payment.get_status_display(),
            payment.pilot_bid.get_status_display(),
            payment.payment_reference or '',
            payment.admin_notes or '',
            payment.created_at.strftime('%Y-%m-%d %H:%M'),
            payment.instructions_sent_at.strftime('%Y-%m-%d %H:%M') if payment.instructions_sent_at else '',
            payment.payment_initiated_at.strftime('%Y-%m-%d %H:%M') if payment.payment_initiated_at else '',
            payment.received_at.strftime('%Y-%m-%d %H:%M') if payment.received_at else '',
            payment.released_at.strftime('%Y-%m-%d %H:%M') if payment.released_at else ''
        ])
    
    return response

@login_required
@staff_member_required
def admin_active_pilots_dashboard(request):
    """Dedicated dashboard for managing active pilot work"""
    
    # Filter and search functionality
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    
    # Base querysets
    base_query = PilotBid.objects.select_related(
        'pilot__organization',
        'startup',
        'payment_holding_service'
    ).prefetch_related('pilot')
    
    # Active pilots (work in progress)
    active_pilots = base_query.filter(status='live')
    
    # Payment confirmed, ready to start work
    ready_to_start = base_query.filter(
        status='approved',
        payment_holding_service__status='received'
    )
    
    # Completion pending (work done, awaiting verification)
    completion_pending = base_query.filter(status='completion_pending')
    
    # Apply search filter
    if search_query:
        search_filter = (
            Q(pilot__title__icontains=search_query) |
            Q(pilot__organization__name__icontains=search_query) |
            Q(startup__name__icontains=search_query)
        )
        active_pilots = active_pilots.filter(search_filter)
        ready_to_start = ready_to_start.filter(search_filter)
        completion_pending = completion_pending.filter(search_filter)
    
    # Apply status filter
    if status_filter == 'live':
        ready_to_start = PilotBid.objects.none()
        completion_pending = PilotBid.objects.none()
    elif status_filter == 'ready':
        active_pilots = PilotBid.objects.none()
        completion_pending = PilotBid.objects.none()
    elif status_filter == 'completion':
        active_pilots = PilotBid.objects.none()
        ready_to_start = PilotBid.objects.none()
    
    # Order by most recent activity
    active_pilots = active_pilots.order_by('-updated_at')
    ready_to_start = ready_to_start.order_by('-updated_at')
    completion_pending = completion_pending.order_by('-updated_at')
    
    # Calculate summary stats
    total_active = active_pilots.count()
    total_ready = ready_to_start.count()
    total_completion = completion_pending.count()
    
    # Calculate total value of active work
    total_active_value = active_pilots.aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    # Average pilot duration (days since went live)
    
    avg_duration = None
    if active_pilots.exists():
        durations = []
        for pilot in active_pilots:
            if pilot.updated_at:  # When it was marked as live
                duration = (timezone.now() - pilot.updated_at).days
                durations.append(duration)
        if durations:
            avg_duration = sum(durations) / len(durations)
    
    context = {
        'active_pilots': active_pilots,
        'ready_to_start': ready_to_start,
        'completion_pending': completion_pending,
        'search_query': search_query,
        'status_filter': status_filter,
        
        # Summary stats
        'total_active': total_active,
        'total_ready': total_ready,
        'total_completion': total_completion,
        'total_active_value': total_active_value,
        'avg_duration': avg_duration,
        
        # Counts for badges
        'all_count': total_active + total_ready + total_completion,
        'live_count': total_active,
        'ready_count': total_ready,
        'completion_count': total_completion,
    }
    
    return render(request, 'admin/payments/admin_active_pilots_dashboard.html', context)

@login_required
@staff_member_required
def admin_start_pilot_work(request, bid_id):
    """Mark a pilot as live (start work) after payment confirmation"""
    if request.method != 'POST':
        return redirect('payments:admin_active_pilots_dashboard')
    
    bid = get_object_or_404(PilotBid, id=bid_id)
    
    # Validate that we can start work
    if bid.status != 'approved':
        messages.error(request, f"Cannot start work. Bid status is '{bid.get_status_display()}', expected 'Approved'.")
        return redirect('payments:admin_active_pilots_dashboard')
    
    # Check that payment is confirmed
    if not hasattr(bid, 'payment_holding_service') or bid.payment_holding_service.status != 'received':
        messages.error(request, "Cannot start work. Payment must be received and confirmed first.")
        return redirect('payments:admin_active_pilots_dashboard')
    
    # Mark as live
    success = bid.mark_live()
    
    if success:
        messages.success(request, f"Work started for pilot '{bid.pilot.title}'. Both parties have been notified.")
    else:
        messages.error(request, "Failed to start work. Please check the bid status.")
    
    return redirect('payments:admin_active_pilots_dashboard')

@login_required
@staff_member_required
def admin_mark_completion_requested(request, bid_id):
    """Admin can mark that startup has requested completion verification"""
    if request.method != 'POST':
        return redirect('payments:admin_active_pilots_dashboard')
    
    bid = get_object_or_404(PilotBid, id=bid_id)
    
    if bid.status != 'live':
        messages.error(request, f"Cannot request completion. Bid must be live. Current status: {bid.get_status_display()}")
        return redirect('payments:admin_active_pilots_dashboard')
    
    success = bid.request_completion()
    
    if success:
        messages.success(request, f"Completion verification requested for '{bid.pilot.title}'. Enterprise has been notified.")
    else:
        messages.error(request, "Failed to request completion verification.")
    
    return redirect('payments:admin_active_pilots_dashboard')

@login_required
@staff_member_required
def admin_contact_pilot_parties(request, bid_id):
    """Admin tool to contact both parties about a pilot"""
    bid = get_object_or_404(PilotBid, id=bid_id)
    
    if request.method == 'POST':
        message_type = request.POST.get('message_type')
        custom_message = request.POST.get('custom_message')
        
        # Send notifications based on message type
        if message_type == 'progress_check':
            title = f"Progress Check: {bid.pilot.title}"
            message = custom_message or f"Admin is checking on the progress of pilot '{bid.pilot.title}'. Please provide an update when convenient."
            
        elif message_type == 'issue_follow_up':
            title = f"Follow-up Required: {bid.pilot.title}"
            message = custom_message or f"Admin follow-up regarding pilot '{bid.pilot.title}'. Please respond at your earliest convenience."
            
        elif message_type == 'completion_reminder':
            title = f"Completion Reminder: {bid.pilot.title}"
            message = custom_message or f"Friendly reminder about pilot '{bid.pilot.title}'. Please mark as complete when work is finished."
            
        else:  # custom
            title = f"Admin Message: {bid.pilot.title}"
            message = custom_message or "Admin message regarding your pilot."
        
        # Send to both enterprise and startup
        from apps.notifications.services import create_notification
        
        # Notify enterprise users
        for user in bid.pilot.organization.users.all():
            create_notification(
                recipient=user,
                notification_type='admin_contact',
                title=title,
                message=message,
                related_pilot=bid.pilot,
                related_bid=bid
            )
        
        # Notify startup users
        for user in bid.startup.users.all():
            create_notification(
                recipient=user,
                notification_type='admin_contact',
                title=title,
                message=message,
                related_pilot=bid.pilot,
                related_bid=bid
            )
        
        messages.success(request, f"Message sent to both {bid.pilot.organization.name} and {bid.startup.name}")
        return redirect('payments:admin_active_pilots_dashboard')
    
    context = {
        'bid': bid,
    }
    
    return render(request, 'admin/payments/admin_contact_pilot_parties.html', context)

# =============================================================================
# FREE ACCOUNT CODES MANAGEMENT
# =============================================================================

@login_required
@staff_member_required
def admin_free_codes_dashboard(request):
    """Main dashboard for Free Account Codes management"""
    # Check if we need to clear generated codes from session
    if request.GET.get('clear_generated_codes') and request.is_ajax():
        if 'generated_codes' in request.session:
            del request.session['generated_codes']
        return JsonResponse({'success': True})
    
    # Get filter parameters
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    plan_filter = request.GET.get('plan', '')
    
    # Base queryset
    codes = FreeAccountCode.objects.select_related('plan', 'created_by').prefetch_related('subscription_set')
    
    # Apply filters
    if search:
        codes = codes.filter(
            Q(code__icontains=search) |
            Q(description__icontains=search) |
            Q(plan__name__icontains=search)
        )
    
    if status_filter == 'active':
        codes = codes.filter(is_active=True, valid_until__gt=timezone.now())
    elif status_filter == 'expired':
        codes = codes.filter(Q(is_active=False) | Q(valid_until__lte=timezone.now()))
    elif status_filter == 'fully_used':
        codes = codes.filter(times_used__gte=F('max_uses'))
    
    if plan_filter:
        codes = codes.filter(plan_id=plan_filter)
    
    # Order by most recent
    codes = codes.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(codes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get statistics
    total_codes = FreeAccountCode.objects.count()
    active_codes = FreeAccountCode.objects.filter(is_active=True, valid_until__gt=timezone.now()).count()
    codes_used_today = FreeAccountCode.objects.filter(
        subscription__created_at__date=timezone.now().date()
    ).distinct().count()
    total_uses = FreeAccountCode.objects.aggregate(total=Sum('times_used'))['total'] or 0
    
    # Get available plans for filter
    available_plans = PricingPlan.objects.filter(is_active=True).order_by('plan_type', 'name')
    
    context = {
        'codes': page_obj,
        'search': search,
        'status_filter': status_filter,
        'plan_filter': plan_filter,
        'available_plans': available_plans,
        'total_codes': total_codes,
        'active_codes': active_codes,
        'codes_used_today': codes_used_today,
        'total_uses': total_uses,
    }
    
    return render(request, 'admin/payments/free_codes/dashboard.html', context)

@login_required
@staff_member_required
def admin_free_code_detail(request, code_id):
    """Detail view for a specific free account code"""
    code = get_object_or_404(
        FreeAccountCode.objects.select_related('plan', 'created_by'),
        id=code_id
    )
    
    # Get all subscriptions using this code
    subscriptions = Subscription.objects.filter(
        free_account_code=code
    ).select_related('organization', 'plan').order_by('-created_at')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'toggle_active':
            code.is_active = not code.is_active
            code.save()
            messages.success(request, f"Code {'activated' if code.is_active else 'deactivated'} successfully")
        
        elif action == 'update':
            # Update code details
            description = request.POST.get('description', '')
            max_uses = request.POST.get('max_uses')
            valid_until = request.POST.get('valid_until')
            
            if description:
                code.description = description
            
            if max_uses:
                try:
                    max_uses = int(max_uses)
                    if max_uses >= code.times_used:
                        code.max_uses = max_uses
                    else:
                        messages.error(request, "Max uses cannot be less than current usage")
                        return redirect('payments:admin_free_code_detail', code_id=code_id)
                except ValueError:
                    messages.error(request, "Invalid max uses value")
                    return redirect('payments:admin_free_code_detail', code_id=code_id)
            
            if valid_until:
                try:
                    valid_until = datetime.strptime(valid_until, '%Y-%m-%d').replace(tzinfo=timezone.get_current_timezone())
                    if valid_until > timezone.now():
                        code.valid_until = valid_until
                    else:
                        messages.error(request, "Valid until date must be in the future")
                        return redirect('payments:admin_free_code_detail', code_id=code_id)
                except ValueError:
                    messages.error(request, "Invalid date format")
                    return redirect('payments:admin_free_code_detail', code_id=code_id)
            
            code.save()
            messages.success(request, "Code updated successfully")
        
        return redirect('payments:admin_free_code_detail', code_id=code_id)
    
    context = {
        'code': code,
        'subscriptions': subscriptions,
        'is_valid': code.is_valid(),
        'can_be_used': code.can_be_used(),
    }
    
    return render(request, 'admin/payments/free_codes/detail.html', context)

@login_required
@staff_member_required
def admin_generate_free_codes(request):
    """Generate new free account codes"""
    if request.method == 'POST':
        try:
            # Get form data
            count = int(request.POST.get('count', 1))
            plan_id = request.POST.get('plan_id')
            description = request.POST.get('description', '')
            valid_days = int(request.POST.get('valid_days', 365))
            free_months = int(request.POST.get('free_months', 12))
            max_uses = int(request.POST.get('max_uses', 1))
            
            # Validate inputs
            if count < 1 or count > 100:
                messages.error(request, "Count must be between 1 and 100")
                return redirect('payments:admin_generate_free_codes')
            
            if not plan_id:
                messages.error(request, "Please select a plan")
                return redirect('payments:admin_generate_free_codes')
            
            if valid_days < 1 or valid_days > 3650:
                messages.error(request, "Valid days must be between 1 and 3650")
                return redirect('payments:admin_generate_free_codes')
            
            if free_months < 1 or free_months > 120:
                messages.error(request, "Free months must be between 1 and 120")
                return redirect('payments:admin_generate_free_codes')
            
            if max_uses < 1 or max_uses > 1000:
                messages.error(request, "Max uses must be between 1 and 1000")
                return redirect('payments:admin_generate_free_codes')
            
            # Get the selected plan
            plan = get_object_or_404(PricingPlan, id=plan_id)
            
            # For annual plans, ensure free_months is a multiple of 12
            if 'yearly' in plan.plan_type and free_months % 12 != 0:
                messages.error(request, f"For annual plans, free months must be a multiple of 12 (e.g., 12, 24, 36). You entered {free_months} months.")
                return redirect('payments:admin_generate_free_codes')
            
            # Generate codes
            generated_codes = []
            for i in range(count):
                code_description = f"{description} ({i+1}/{count})" if count > 1 and description else description
                code = FreeAccountCode.generate_code(
                    plan=plan,
                    description=code_description or f"Generated {timezone.now().strftime('%Y-%m-%d')}",
                    valid_days=valid_days,
                    max_uses=max_uses,
                    free_months=free_months,
                    created_by=request.user
                )
                generated_codes.append(code)
            
            # Store codes in session for display
            request.session['generated_codes'] = [code.code for code in generated_codes]
            
            messages.success(request, f"Successfully generated {count} free account codes!")
            return redirect('payments:admin_free_codes_dashboard')
            
        except ValueError as e:
            messages.error(request, f"Invalid input: {str(e)}")
        except Exception as e:
            messages.error(request, f"Error generating codes: {str(e)}")
    
    # GET request - show form
    plans = PricingPlan.objects.filter(is_active=True).order_by('plan_type', 'name')
    
    context = {
        'plans': plans,
    }
    
    return render(request, 'admin/payments/free_codes/generate.html', context)

@login_required
@staff_member_required
def admin_export_free_codes_csv(request):
    """Export free account codes as CSV"""
    # Apply same filters as dashboard
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')
    plan_filter = request.GET.get('plan', '')
    
    # Base queryset
    codes = FreeAccountCode.objects.select_related('plan', 'created_by')
    
    # Apply filters
    if search:
        codes = codes.filter(
            Q(code__icontains=search) |
            Q(description__icontains=search) |
            Q(plan__name__icontains=search)
        )
    
    if status_filter == 'active':
        codes = codes.filter(is_active=True, valid_until__gt=timezone.now())
    elif status_filter == 'expired':
        codes = codes.filter(Q(is_active=False) | Q(valid_until__lte=timezone.now()))
    elif status_filter == 'fully_used':
        codes = codes.filter(times_used__gte=F('max_uses'))
    
    if plan_filter:
        codes = codes.filter(plan_id=plan_filter)
    
    # Order by most recent
    codes = codes.order_by('-created_at')
    
    # Create the HttpResponse with CSV header
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="free_account_codes_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Code', 'Plan Name', 'Plan Type', 'Plan Price', 'Description', 'Free Months', 
        'Times Used', 'Max Uses', 'Remaining Uses', 'Is Active', 'Currently Valid',
        'Valid From', 'Valid Until', 'Days Until Expiry', 'Created At', 'Created By',
        'Organizations Using Code'
    ])
    
    # Prefetch subscriptions using the codes
    codes = codes.prefetch_related('subscription_set__organization')
    
    for code in codes:
        # Calculate days until expiry
        days_until_expiry = (code.valid_until - timezone.now()).days if code.valid_until > timezone.now() else 0
        
        # Get organizations using this code
        orgs_using_code = []
        for subscription in code.subscription_set.all():
            orgs_using_code.append(subscription.organization.name)
        orgs_using_code_str = '; '.join(orgs_using_code) if orgs_using_code else 'None'
        
        writer.writerow([
            code.code,
            code.plan.name,
            code.plan.get_plan_type_display(),
            f"${code.plan.price}",
            code.description,
            code.free_months,
            code.times_used,
            code.max_uses,
            code.max_uses - code.times_used,
            'Yes' if code.is_active else 'No',
            'Yes' if code.is_valid() else 'No',
            code.valid_from.strftime('%Y-%m-%d %H:%M'),
            code.valid_until.strftime('%Y-%m-%d %H:%M'),
            days_until_expiry if days_until_expiry > 0 else 'Expired',
            code.created_at.strftime('%Y-%m-%d %H:%M'),
            code.created_by.get_full_name() if code.created_by else 'System',
            orgs_using_code_str
        ])
    
    return response


@staff_member_required
def admin_bulk_delete_free_codes(request):
    """Handle bulk deletion of free account codes"""
    if request.method != 'POST':
        messages.error(request, "Invalid request method")
        return redirect('payments:admin_free_codes_dashboard')
    
    selected_codes = request.POST.getlist('selected_codes')
    
    if not selected_codes:
        messages.error(request, "No codes were selected for deletion")
        return redirect('payments:admin_free_codes_dashboard')
    
    try:
        # Get the codes to be deleted
        codes_to_delete = FreeAccountCode.objects.filter(id__in=selected_codes)
        deleted_count = codes_to_delete.count()
        
        # Get some info for the success message
        deleted_info = []
        for code in codes_to_delete[:5]:  # Show first 5 codes in message
            deleted_info.append(f"{code.code} ({code.plan.name})")
        
        # Delete the codes
        codes_to_delete.delete()
        
        # Create success message
        if deleted_count <= 5:
            codes_list = ", ".join(deleted_info)
            messages.success(request, f"Successfully deleted {deleted_count} code{'s' if deleted_count != 1 else ''}: {codes_list}")
        else:
            first_five = ", ".join(deleted_info)
            messages.success(request, f"Successfully deleted {deleted_count} codes including: {first_five} and {deleted_count - 5} more")
        
    except Exception as e:
        messages.error(request, f"Error deleting codes: {str(e)}")
    
    return redirect('payments:admin_free_codes_dashboard')