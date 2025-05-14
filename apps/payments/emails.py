from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)

def send_subscription_confirmation(user, subscription):
    """Send subscription confirmation email to user"""
    try:
        # Determine the subscription type and plan details
        plan_name = subscription.plan.name
        plan_price = subscription.plan.price
        plan_frequency = subscription.plan.billing_frequency
        organization_name = subscription.organization.name
        organization_type = subscription.organization.get_type_display()
        
        # Calculate pilot limit for display
        if subscription.plan.pilot_limit is None:
            pilot_limit_text = "Unlimited pilots"
        else:
            pilot_limit_text = f"{subscription.plan.pilot_limit} pilots per {plan_frequency}"
        
        # Prepare email context
        context = {
            'user': user,
            'organization_name': organization_name,
            'organization_type': organization_type,
            'plan_name': plan_name,
            'plan_price': plan_price,
            'plan_frequency': plan_frequency,
            'pilot_limit_text': pilot_limit_text,
            'subscription': subscription,
            'dashboard_url': settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'marketplace.fend.ai',
        }
        
        # Render email templates
        subject = f'Welcome to Fend Marketplace - {plan_name} Subscription Confirmed'
        html_message = render_to_string('emails/subscription_confirmation.html', context)
        text_message = strip_tags(html_message)
        
        # Send email
        send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Subscription confirmation email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send subscription confirmation email to {user.email}: {str(e)}")
        return False

def send_subscription_renewal_email(user, subscription):
    """Send subscription renewal notification"""
    try:
        context = {
            'user': user,
            'subscription': subscription,
            'organization_name': subscription.organization.name,
            'next_billing_date': subscription.current_period_end,
            'plan_name': subscription.plan.name,
            'plan_price': subscription.plan.price,
        }
        
        subject = 'Your Fend Marketplace Subscription Has Been Renewed'
        html_message = render_to_string('emails/subscription_renewal.html', context)
        text_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Subscription renewal email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send subscription renewal email to {user.email}: {str(e)}")
        return False

def send_payment_received_email(user, payment):
    """Send payment received confirmation"""
    try:
        context = {
            'user': user,
            'payment': payment,
            'organization_name': payment.organization.name,
            'amount': payment.amount,
            'payment_type': payment.get_payment_type_display(),
        }
        
        subject = f'Payment Received - ${payment.amount}'
        html_message = render_to_string('emails/payment_received.html', context)
        text_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Payment received email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send payment received email to {user.email}: {str(e)}")
        return False
    
def send_verification_email(user, verification_url):
    """Send email verification to new user"""
    try:
        context = {
            'user': user,
            'verification_url': verification_url,
            'organization_name': user.organization.name if user.organization else '',
        }
        
        subject = 'Verify Your Email - Fend Marketplace'
        html_message = render_to_string('emails/email_verification.html', context)
        text_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Verification email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send verification email to {user.email}: {str(e)}")
        return False

def send_welcome_email(user):
    """Send welcome email after verification"""
    try:
        context = {
            'user': user,
            'organization_name': user.organization.name if user.organization else '',
            'dashboard_url': settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'marketplace.fend.ai',
        }
        
        subject = 'Welcome to Fend Marketplace!'
        html_message = render_to_string('emails/welcome.html', context)
        text_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Welcome email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send welcome email to {user.email}: {str(e)}")
        return False