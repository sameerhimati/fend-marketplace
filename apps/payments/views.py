from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from apps.pilots.models import PilotTransaction
from apps.notifications.services import create_bid_notification, create_pilot_notification

from .models import PricingPlan, Subscription, Payment
from apps.organizations.models import Organization

import stripe
import json
from datetime import datetime, timedelta

# Set your Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY

@login_required
def payment_selection(request):
    """Show payment plan selection after registration"""
    organization = request.user.organization
    
    # If organization already has active subscription, redirect to dashboard
    if organization.has_active_subscription():
        return redirect('organizations:dashboard')
    
    # Get available plans based on organization type
    available_plans = PricingPlan.get_available_plans(organization.type)
    
    if request.method == 'POST':
        plan_id = request.POST.get('plan_id')
        
        if not plan_id:
            messages.error(request, "Please select a plan")
            return render(request, 'payments/plan_selection.html', {
                'plans': available_plans,
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
                'plans': available_plans,
                'organization': organization
            })
    
    return render(request, 'payments/plan_selection.html', {
        'plans': available_plans,
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
            Payment.objects.create(
                organization=organization,
                subscription=subscription,
                payment_type='subscription',
                amount=subscription.plan.price,
                stripe_payment_id=payment_id,
                status='complete'
            )
        
        # If one-time payment mode
        elif session.mode == 'payment':
            subscription.status = 'active'
            
            # Set subscription period for one-time enterprise plans (1 year)
            if subscription.plan.plan_type == 'enterprise_single':
                subscription.current_period_start = timezone.now()
                subscription.current_period_end = timezone.now() + timedelta(days=365)
                
            subscription.save()
            
            # Create a payment record
            payment_id = session.payment_intent or session.id
            Payment.objects.create(
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
        # Invalid payload
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
                
                # Mark organization as having completed payment
                organization.onboarding_completed = True
                organization.has_payment_method = True
                organization.save()
                
                # Create payment record if not exists
                Payment.objects.get_or_create(
                    organization=organization,
                    subscription=subscription,
                    payment_type='subscription',
                    defaults={
                        'amount': subscription.plan.price,
                        'stripe_payment_id': session.payment_intent,
                        'status': 'complete'
                    }
                )
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
            Payment.objects.create(
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
        
        # Cancel at period end
        if subscription.stripe_subscription_id:
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
def upgrade_subscription(request):
    """Upgrade or change subscription plan"""
    organization = request.user.organization
    
    # Get available plans based on organization type
    available_plans = PricingPlan.get_available_plans(organization.type)
    
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
                'plans': available_plans,
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
                    'plans': available_plans,
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
                    'plans': available_plans,
                    'current_subscription': current_subscription
                })
    
    return render(request, 'payments/upgrade_subscription.html', {
        'plans': available_plans,
        'current_subscription': current_subscription
    })

@login_required
def process_transaction(request, transaction_id):
    """Process a pilot transaction payment"""
    transaction = get_object_or_404(PilotTransaction, id=transaction_id)
    
    # Check if user is authorized (startup that submitted the bid)
    if request.user.organization != transaction.pilot_bid.startup:
        messages.error(request, "You don't have permission to process this payment")
        return redirect('pilots:bid_detail', pk=transaction.pilot_bid.id)
    
    # Check if transaction is pending
    if transaction.status != 'pending':
        messages.error(request, "This transaction is already being processed")
        return redirect('pilots:bid_detail', pk=transaction.pilot_bid.id)
    
    try:
        # Create Stripe PaymentIntent
        intent = stripe.PaymentIntent.create(
            amount=int(transaction.amount * 100),  # Convert to cents
            currency='usd',
            customer=request.user.organization.stripe_customer_id,
            metadata={
                'transaction_id': transaction.id,
                'pilot_bid_id': transaction.pilot_bid.id,
                'pilot_title': transaction.pilot_bid.pilot.title
            }
        )
        
        # Update transaction with PaymentIntent ID
        transaction.stripe_payment_intent_id = intent.id
        transaction.status = 'processing'
        transaction.save()
        
        # Create checkout session for the PaymentIntent
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            payment_intent=intent.id,
            client_reference_id=str(transaction.id),
            customer=request.user.organization.stripe_customer_id,
            success_url=request.build_absolute_uri(
                reverse('payments:transaction_success', args=[transaction.id])
            ),
            cancel_url=request.build_absolute_uri(
                reverse('payments:transaction_cancel', args=[transaction.id])
            ),
        )
        
        return redirect(checkout_session.url)
    
    except Exception as e:
        messages.error(request, f"Error processing payment: {str(e)}")
        return redirect('pilots:bid_detail', pk=transaction.pilot_bid.id)

@login_required
def transaction_success(request, transaction_id):
    """Handle successful transaction payment"""
    transaction = get_object_or_404(PilotTransaction, id=transaction_id)
    
    # Mark transaction as completed
    transaction.status = 'completed'
    transaction.completed_at = timezone.now()
    transaction.save()
    
    # Mark bid as paid
    bid = transaction.pilot_bid
    bid.status = 'paid'
    bid.save()
    
    # Create notifications
    create_bid_notification(
        bid=bid,
        notification_type='payment_received',
        title=f"Payment completed: {bid.pilot.title}",
        message=f"Payment of ${transaction.amount} has been processed for pilot '{bid.pilot.title}'."
    )
    
    messages.success(request, "Payment completed successfully!")
    return redirect('pilots:bid_detail', pk=bid.id)

@login_required
def transaction_cancel(request, transaction_id):
    """Handle cancelled transaction payment"""
    transaction = get_object_or_404(PilotTransaction, id=transaction_id)
    
    # Reset transaction status
    transaction.status = 'pending'
    transaction.save()
    
    messages.warning(request, "Payment was cancelled. You can try again later.")
    return redirect('pilots:bid_detail', pk=transaction.pilot_bid.id)