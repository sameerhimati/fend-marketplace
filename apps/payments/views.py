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
from apps.pilots.models import PilotTransaction, PilotBid
from apps.notifications.services import create_bid_notification, create_pilot_notification, create_notification

from .models import PricingPlan, Subscription, Payment, EscrowPayment, EscrowPaymentLog
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
        transaction_id = session.metadata.get('transaction_id')

        # if transaction_id:
        #     try:
        #         transaction = TokenTransaction.objects.get(id=transaction_id)
                
        #         # Update transaction with payment intent
        #         transaction.stripe_payment_id = session.payment_intent or session.id
                
        #         transaction.mark_completed()
                
        #         print(f"Token purchase completed: {transaction}")
        #     except TokenTransaction.DoesNotExist:
        #         print(f"Error processing token transaction: Transaction {transaction_id} not found")
        #     except Exception as e:
        #         print(f"Error processing token transaction: {e}")
        
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
        # Total amount including startup's fee portion
        total_amount = transaction.amount + transaction.fee_amount
        
        # Create Stripe PaymentIntent
        intent = stripe.PaymentIntent.create(
            amount=int(total_amount * 100),  # Convert to cents
            currency='usd',
            customer=request.user.organization.stripe_customer_id,
            metadata={
                'transaction_id': transaction.id,
                'pilot_bid_id': transaction.pilot_bid.id,
                'pilot_title': transaction.pilot_bid.pilot.title,
                'base_amount': float(transaction.amount),
                'fee_amount': float(transaction.fee_amount),
                'fee_percentage': float(transaction.fee_percentage)
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

@login_required
@staff_member_required
def admin_escrow_payment_detail(request, payment_id):
    """Admin view for a single escrow payment"""
    payment = get_object_or_404(EscrowPayment, id=payment_id)
    
    return render(request, 'payments/admin_escrow_payment_detail.html', {
        'payment': payment
    })

@login_required
@staff_member_required
def admin_mark_payment_received(request, payment_id):
    """Admin marks payment as received"""
    if request.method != 'POST':
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    payment = get_object_or_404(EscrowPayment, id=payment_id)
    
    # Create log entry
    EscrowPaymentLog.objects.create(
        escrow_payment=payment,
        previous_status=payment.status,
        new_status='received',
        changed_by=request.user,
        notes=request.POST.get('notes', '')
    )
    
    # Mark payment as received
    payment.mark_as_received()
    
    messages.success(request, f"Payment {payment.reference_code} marked as received")
    return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)

@login_required
@staff_member_required
def admin_release_payment(request, payment_id):
    """Admin releases payment to startup"""
    if request.method != 'POST':
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    payment = get_object_or_404(EscrowPayment, id=payment_id)
    
    # Check if payment is in received status
    if payment.status != 'received':
        messages.error(request, "Payment must be in 'received' status to be released")
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    # Check if pilot is marked as completed
    if payment.pilot_bid.status != 'completed':
        messages.error(request, "The pilot must be marked as completed by the enterprise before releasing payment")
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    # Create log entry
    EscrowPaymentLog.objects.create(
        escrow_payment=payment,
        previous_status=payment.status,
        new_status='released',
        changed_by=request.user,
        notes=request.POST.get('notes', '')
    )
    
    # Mark payment as released
    payment.mark_as_released()
    
    messages.success(request, f"Payment {payment.reference_code} released to startup")
    return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)

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
        
        # Special handling for 'approved' status
        if new_status == 'approved':
            # Create escrow payment
            escrow_payment = bid.mark_as_approved()
            
            if escrow_payment:
                # Redirect to payment instructions
                messages.success(request, f"Bid status updated from {valid_statuses[old_status]} to {valid_statuses[new_status]}")
                return redirect('payments:escrow_payment_instructions', payment_id=escrow_payment.id)
            else:
                messages.error(request, "Error creating escrow payment record")
                return redirect('pilots:bid_detail', pk=pk)
        else:
            # Normal status update
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
def finalize_pilot(request, pk):
    """Mark a pilot as completed and trigger payment release"""
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
    
    # Notify admins that the pilot is completed and payment is ready for release
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


@login_required
@staff_member_required
def admin_payment_dashboard(request):
    """Admin dashboard focusing on actionable items"""
    
    # Payments needing verification (initiated but not received)
    needs_verification = EscrowPayment.objects.filter(
        status='payment_initiated'
    ).order_by('-payment_initiated_at')[:5]  # Limit to 5 most recent
    
    # Payments ready for release (received and pilot completed)
    ready_for_release = EscrowPayment.objects.filter(
        status='received', 
        pilot_bid__status='completed'
    ).order_by('-received_at')[:5]  # Limit to 5 most recent
    
    # Recent activity
    recent_logs = EscrowPaymentLog.objects.order_by('-created_at')[:5]
    
    return render(request, 'payments/admin_payment_dashboard.html', {
        'needs_verification': needs_verification,
        'ready_for_release': ready_for_release,
        'recent_logs': recent_logs,
    })

@login_required
@staff_member_required
def admin_escrow_payments(request):
    """Enhanced admin view for escrow payments"""
    tab = request.GET.get('tab')
    search = request.GET.get('search')
    status = request.GET.get('status')
    
    # Base queryset
    payments = EscrowPayment.objects.all()
    
    # Apply tab filter
    if tab == 'initiated':
        payments = payments.filter(status='payment_initiated')
    elif tab == 'ready':
        payments = payments.filter(status='received', pilot_bid__status='completed')
    elif tab == 'completed':
        payments = payments.filter(status='released')
    
    # Apply search filter
    if search:
        payments = payments.filter(
            Q(reference_code__icontains=search) | 
            Q(pilot_bid__pilot__title__icontains=search) |
            Q(pilot_bid__pilot__organization__name__icontains=search) |
            Q(pilot_bid__startup__name__icontains=search)
        )
    
    # Apply status filter
    if status:
        payments = payments.filter(status=status)
    
    # Order by most recent activity
    payments = payments.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(payments, 10)  # Show 10 payments per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get counts for tabs
    initiated_count = EscrowPayment.objects.filter(status='payment_initiated').count()
    ready_count = EscrowPayment.objects.filter(status='received', pilot_bid__status='completed').count()
    released_count = EscrowPayment.objects.filter(status='released').count()
    pending_count = EscrowPayment.objects.filter(
        Q(status='pending') | Q(status='instructions_sent')
    ).count()
    
    return render(request, 'payments/admin_escrow_payments.html', {
        'payments': page_obj,
        'tab': tab,
        'initiated_count': initiated_count,
        'ready_count': ready_count,
        'released_count': released_count,
        'pending_count': pending_count,
    })

@login_required
@staff_member_required
def admin_update_payment_status(request, payment_id):
    """Update payment status manually"""
    if request.method != 'POST':
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    payment = get_object_or_404(EscrowPayment, id=payment_id)
    new_status = request.POST.get('status')
    notes = request.POST.get('notes', '')
    
    # Validate status
    valid_statuses = dict(EscrowPayment.STATUS_CHOICES)
    if new_status not in valid_statuses:
        messages.error(request, "Invalid status")
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    # Don't update if status hasn't changed
    if new_status == payment.status:
        messages.info(request, "Status unchanged")
        return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)
    
    # Special handling for released status - check pilot completion
    if new_status == 'released' and payment.pilot_bid.status != 'completed':
        # We'll allow it with a warning
        messages.warning(request, "Warning: Releasing payment before pilot completion was marked")
    
    # Create log entry
    EscrowPaymentLog.objects.create(
        escrow_payment=payment,
        previous_status=payment.status,
        new_status=new_status,
        changed_by=request.user,
        notes=notes
    )
    
    # Special handling for specific statuses
    if new_status == 'received':
        payment.mark_as_received()
    elif new_status == 'released':
        payment.mark_as_released()
    else:
        # Generic status update
        payment.status = new_status
        payment.save(update_fields=['status'])
    
    messages.success(request, f"Payment status updated to {valid_statuses[new_status]}")
    return redirect('payments:admin_escrow_payment_detail', payment_id=payment_id)

@login_required
@staff_member_required
def admin_export_payments_csv(request):
    """Export payments as CSV file"""
    # Apply same filters as admin_escrow_payments
    tab = request.GET.get('tab')
    search = request.GET.get('search')
    status = request.GET.get('status')
    
    # Base queryset
    payments = EscrowPayment.objects.all()
    
    # Apply filters (same as in list view)
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
    
    if status:
        payments = payments.filter(status=status)
    
    # Order by most recent activity
    payments = payments.order_by('-created_at')
    
    # Create the HttpResponse with CSV header
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="escrow_payments_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Reference Code', 'Pilot Title', 'Enterprise', 'Startup', 
        'Amount', 'Status', 'Created Date', 'Last Updated'
    ])
    
    for payment in payments:
        # Determine last updated date based on status
        if payment.released_at:
            last_updated = payment.released_at
        elif payment.received_at:
            last_updated = payment.received_at
        elif payment.payment_initiated_at:
            last_updated = payment.payment_initiated_at
        elif payment.instructions_sent_at:
            last_updated = payment.instructions_sent_at
        else:
            last_updated = payment.created_at
            
        writer.writerow([
            payment.reference_code,
            payment.pilot_bid.pilot.title,
            payment.pilot_bid.pilot.organization.name,
            payment.pilot_bid.startup.name,
            payment.total_amount,
            payment.get_status_display(),
            payment.created_at.strftime('%Y-%m-%d'),
            last_updated.strftime('%Y-%m-%d')
        ])
    
    return response