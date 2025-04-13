# apps/payments/middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from django.contrib import messages

class SubscriptionRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Define paths that DO NOT require an active subscription check
        # Keep this list specific and comprehensive
        self.exempt_paths_prefixes = [
            '/admin/',
            settings.STATIC_URL,
            settings.MEDIA_URL,
            '/payments/', # Exempt ALL URLs starting with /payments/
            reverse('landing'), # The root path
            reverse('organizations:login'),
            reverse('organizations:logout'),
            reverse('organizations:register'),
            reverse('organizations:registration_complete'),
            '/notifications/count/', # Exempt notification count API
        ]
        # Clean up potential None values from settings
        self.exempt_paths_prefixes = [p for p in self.exempt_paths_prefixes if p is not None]

    def is_path_exempt(self, path):
        """Check if the requested path starts with any exempt prefix."""
        for prefix in self.exempt_paths_prefixes:
            # Make sure prefix is a string before calling startswith
            if isinstance(prefix, str) and path.startswith(prefix):
                return True
        return False

    def __call__(self, request):
        # Allow anonymous users
        if not request.user.is_authenticated:
            # If trying to access protected content, redirect to landing
            if not self.is_path_exempt(request.path) and request.path != '/':
                return redirect('landing')
            return self.get_response(request)

        # Allow access to exempt paths always
        if self.is_path_exempt(request.path):
            return self.get_response(request)

        # --- Path is NOT exempt, user IS authenticated ---

        # Check for organization (should exist for authenticated users)
        if not hasattr(request.user, 'organization') or not request.user.organization:
            # This is an unexpected state, redirect to landing/login
            messages.error(request, "Your account needs to be properly set up. Please sign out and register again.")
            return redirect('landing')

        # Check for active subscription
        if not request.user.organization.has_active_subscription():
            # User needs a subscription, redirect them ONCE to the detail page
            # Only add the message if not already on the target page to avoid duplicate messages on loop attempt
            if request.path != reverse('payments:subscription_detail'):
                 messages.warning(request, "You need an active subscription to access this feature.")
            return redirect('payments:subscription_detail') # Redirect ALL users without active sub here

        # If user is authenticated, path not exempt, and subscription is active, allow access
        return self.get_response(request)