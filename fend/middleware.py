# fend/middleware.py
class AuthenticationFlowMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Just pass through during initial testing phase
        response = self.get_response(request)
        return response

# When ready to enable:
"""
class AuthenticationFlowMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
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
                    from django.shortcuts import redirect
                    return redirect('payments:payment_selection')
        
        response = self.get_response(request)
        return response
"""