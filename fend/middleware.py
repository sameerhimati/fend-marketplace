from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages

class AuthenticationFlowMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Skip all checks for staff and superusers
            if request.user.is_staff or request.user.is_superuser:
                return self.get_response(request)
                
            # Paths always accessible regardless of status
            always_accessible_paths = [
                '/admin/',
                '/organizations/logout/',
                '/static/',
                '/media/',
            ]
            
            # Check if current path is in always accessible paths
            is_always_accessible = any(
                request.path.startswith(path) for path in always_accessible_paths
            )
            
            # If user has organization (should have after registration)
            if hasattr(request.user, 'organization') and request.user.organization:
                # If organization is pending approval
                if request.user.organization.approval_status == 'pending':
                    # Only allow pending-approval page and payment-related paths
                    pending_allowed_paths = [
                        '/organizations/pending-approval/',
                        '/payments/', # Allow access to payment processing
                    ]
                    
                    is_pending_allowed = any(
                        request.path.startswith(path) for path in pending_allowed_paths
                    )
                    
                    if not is_always_accessible and not is_pending_allowed:
                        # Force redirect to pending approval page
                        return redirect('organizations:pending_approval')
                
                # If organization was rejected
                elif request.user.organization.approval_status == 'rejected':
                    if not is_always_accessible and request.path != reverse('organizations:logout'):
                        messages.error(request, "Your account application has been rejected.")
                        return redirect('organizations:logout')
                
                # If organization is approved, handle subscription check
                elif request.user.organization.approval_status == 'approved':
                    # Check subscription status
                    subscription_exempt_paths = [
                        '/payments/',
                    ]
                    
                    is_subscription_exempt = any(
                        request.path.startswith(path) for path in subscription_exempt_paths
                    ) or is_always_accessible
                    
                    if not is_subscription_exempt:
                        # If trying to access dashboard without subscription
                        if not request.user.organization.has_active_subscription():
                            if request.path == '/organizations/dashboard/' or request.path == '/':
                                message_text = "You need an active subscription to access the dashboard."
                                messages.warning(request, message_text)
                                return redirect('payments:subscription_detail')
                
        response = self.get_response(request)
        return response