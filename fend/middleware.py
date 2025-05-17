from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages

class AuthenticationFlowMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Skip approval check for these paths
            approval_exempt_paths = [
                '/admin/',
                '/organizations/pending-approval/',
                '/organizations/logout/',
                '/static/',
                '/media/',
                '/payments/', # Allow access to payment processing
            ]
            
            # Check if current path is exempt from approval check
            is_approval_exempt = any(
                request.path.startswith(path) for path in approval_exempt_paths
            )
            
            # Skip approval check for staff and superusers
            if not request.user.is_staff and not request.user.is_superuser:
                # If user has organization (should have after registration)
                if hasattr(request.user, 'organization') and request.user.organization:
                    # If organization is pending approval
                    if request.user.organization.approval_status == 'pending':
                        if not is_approval_exempt:
                            # Redirect to pending approval page
                            return redirect('organizations:pending_approval')
                    
                    # If organization was rejected
                    elif request.user.organization.approval_status == 'rejected':
                        if not is_approval_exempt and request.path != reverse('organizations:logout'):
                            messages.error(request, "Your account application has been rejected.")
                            return redirect('organizations:logout')
                    
                    # If organization is approved, handle subscription check
                    elif request.user.organization.approval_status == 'approved':
                        # Check subscription status (use existing logic)
                        subscription_exempt_paths = [
                            '/admin/',
                            '/static/',
                            '/media/',
                            '/payments/',
                            '/organizations/logout/',
                        ]
                        
                        is_subscription_exempt = any(
                            request.path.startswith(path) for path in subscription_exempt_paths
                        )
                        
                        if not is_subscription_exempt:
                            # If trying to access dashboard without subscription
                            if not request.user.organization.has_active_subscription():
                                if request.path == '/organizations/dashboard/' or request.path == '/':
                                    if request.user.organization.type == 'startup':
                                        messages.warning(request, "Your startup account requires an active subscription to access the dashboard.")
                                    else:
                                        messages.warning(request, "You need an active subscription to access the dashboard.")
                                    return redirect('payments:subscription_detail')
                
            # Staff/admin users get special handling
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
                
        response = self.get_response(request)
        return response