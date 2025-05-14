from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages

class AuthenticationFlowMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Skip verification check for these paths
            verification_exempt_paths = [
                '/admin/',
                '/organizations/verify-email/',
                '/organizations/verification-pending/',
                '/organizations/resend-verification/',
                '/organizations/logout/',
                '/static/',
                '/media/',
                '/payments/',  # Add this to allow payment access after verification
            ]
            
            # Check if current path is exempt from verification
            is_verification_exempt = any(
                request.path.startswith(path) for path in verification_exempt_paths
            )
            
            # If user is not verified and not on an exempt path
            if not hasattr(request.user, 'is_verified') or not request.user.is_verified:
                if not is_verification_exempt:
                    messages.warning(request, "Please verify your email address to continue.")
                    return redirect('organizations:verification_pending')

            # Handle staff users
            if request.user.is_staff:
                if (
                    request.path.startswith('/admin/') or 
                    request.path.startswith('/payments/admin/')
                ):
                    return self.get_response(request)
                if request.path == '/':
                    return redirect('admin:index')
                if request.path == '/organizations/dashboard/':
                    return redirect('admin:index')
                
                return self.get_response(request)
            
            # Check if user has organization (should have after registration)
            if not hasattr(request.user, 'organization') or not request.user.organization:
                # This shouldn't happen for verified users, but just in case
                from django.contrib.auth import logout
                logout(request)
                messages.warning(request, "Your session has expired. Please log in again.")
                return redirect('landing')
            
            # Handle dashboard redirection based on subscription
            if request.path == '/' or request.path == '/organizations/dashboard/':
                # For users without active subscription trying to access dashboard
                if request.path == '/organizations/dashboard/' and not request.user.organization.has_active_subscription():
                    if request.user.organization.type == 'startup':
                        messages.warning(request, "Your startup account requires an active subscription to access the dashboard.")
                    else:
                        messages.warning(request, "You need an active subscription to access the dashboard.")
                    return redirect('payments:subscription_detail')
                
                # For authenticated users with subscription on landing page
                if request.path == '/' and request.user.organization.has_active_subscription():
                    return redirect('organizations:dashboard')
            
            # Check if user has completed onboarding (this includes having a subscription)
            if not request.user.organization.onboarding_completed:
                # For verified users who haven't completed payment yet
                allowed_paths = [
                    '/payments/',  # Allow all payment paths
                    '/organizations/logout/',
                    '/static/',
                    '/media/',
                    '/admin/',
                ]
                
                # Check if current path is allowed
                is_allowed = any(request.path.startswith(path) for path in allowed_paths)
                
                if not is_allowed:
                    # Redirect to payment selection for verified but unpaid users
                    return redirect('payments:payment_selection')
        
        response = self.get_response(request)
        return response