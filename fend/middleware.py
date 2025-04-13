from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages

class AuthenticationFlowMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Handle dashboard redirection based on subscription
            if request.path == '/' or request.path == '/organizations/dashboard/':
                # Check if user has valid subscription
                if not hasattr(request.user, 'organization') or not request.user.organization:
                    # This shouldn't happen, but just in case - log them out
                    from django.contrib.auth import logout
                    logout(request)
                    messages.warning(request, "Your session has expired. Please log in again.")
                    return redirect('landing')
                
                # For users without active subscription trying to access dashboard
                # Explicitly handle both startups and enterprises
                if request.path == '/organizations/dashboard/' and not request.user.organization.has_active_subscription():
                    if request.user.organization.type == 'startup':
                        messages.warning(request, "Your startup account requires an active subscription to access the dashboard.")
                    else:
                        messages.warning(request, "You need an active subscription to access the dashboard.")
                    return redirect('payments:subscription_detail')
                
                # For authenticated users with subscription on landing page
                if request.path == '/' and request.user.organization.has_active_subscription():
                    return redirect('organizations:dashboard')
            
            # Check if user has completed onboarding
            if not hasattr(request.user, 'organization') or not request.user.organization.onboarding_completed:
                # Allow access only to payment pages and logout
                allowed_paths = [
                    '/payments/select-plan/',
                    '/payments/checkout/success/',
                    '/payments/checkout/cancel/',
                    '/organizations/logout/',
                    '/static/',
                    '/media/',
                    '/admin/',
                ]
                
                # Check if current path is allowed
                is_allowed = False
                for path in allowed_paths:
                    if request.path.startswith(path):
                        is_allowed = True
                        break
                
                if not is_allowed:
                    # Redirect to payment selection if onboarding not completed
                    return redirect('payments:payment_selection')
        
        response = self.get_response(request)
        return response