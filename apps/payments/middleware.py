from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages

class SubscriptionRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process request - check for subscription before accessing protected views
        if request.user.is_authenticated and request.user.organization.type == 'startup':
            # Exempt paths that should be accessible without subscription
            exempt_paths = [
                reverse('payments:payment_selection'),
                reverse('payments:subscription_detail'),
                reverse('payments:checkout_success'),
                reverse('payments:checkout_cancel'),
                reverse('payments:stripe_webhook'),
                '/static/',
                '/media/',
                '/admin/',
            ]
            
            # Check if current path is exempt
            if not any(request.path.startswith(path) for path in exempt_paths):
                # Check if organization has active subscription
                if not request.user.organization.has_active_subscription():
                    messages.warning(request, "You need an active subscription to access this feature.")
                    return redirect('payments:subscription_detail')
        
        response = self.get_response(request)
        return response