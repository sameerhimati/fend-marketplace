# apps/payments/middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages

class SubscriptionRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # All paths are exempt during initial testing
        self.exempt_paths_prefixes = [
            '/',  # Exempt everything for now
        ]

    def is_path_exempt(self, path):
        """Check if the requested path starts with any exempt prefix."""
        # Always return True during initial testing
        return True

    def __call__(self, request):
        # Just pass through to the next middleware/view for now
        return self.get_response(request)

# When you're ready to enable actual subscription checks, replace the middleware with:
# """
# class SubscriptionRequiredMiddleware:
#     def __init__(self, get_response):
#         self.get_response = get_response
#         # Define paths that DO NOT require an active subscription check
#         self.exempt_paths_prefixes = [
#             '/admin/',
#             '/static/',
#             '/media/',
#             '/payments/', 
#             '/',  # The root path
#             '/organizations/login/',
#             '/organizations/logout/',
#             '/organizations/register/',
#             '/organizations/registration_complete/',
#             '/notifications/count/', 
#         ]

#     def is_path_exempt(self, path):
#         """Check if the requested path starts with any exempt prefix."""
#         for prefix in self.exempt_paths_prefixes:
#             if path.startswith(prefix):
#                 return True
#         return False

#     def __call__(self, request):
#         # Allow anonymous users
#         if not request.user.is_authenticated:
#             return self.get_response(request)

#         # Allow access to exempt paths always
#         if self.is_path_exempt(request.path):
#             return self.get_response(request)

#         # Check if user has organization
#         if not hasattr(request.user, 'organization') or not request.user.organization:
#             # Redirect to landing (they need to register/login properly)
#             return redirect('landing')

#         # Check for active subscription
#         if not request.user.organization.has_active_subscription():
#             # Only add message if not already on subscription page
#             if request.path != reverse('payments:subscription_detail'):
#                 messages.warning(request, "You need an active subscription to access this feature.")
#             return redirect('payments:subscription_detail')

#         # If all checks pass, allow access
#         return self.get_response(request)
# """