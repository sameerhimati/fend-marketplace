# fend/middleware.py

from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)

class AuthenticationFlowMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Default UI state - full navigation
        request.ui_state = 'full'
        
        if request.user.is_authenticated:
            # Debug log to see what's happening
            if '/organizations/logout/' in request.path and request.method == 'GET':
                logger.warning(f"GET request to logout detected: {request.path}, Referer: {request.META.get('HTTP_REFERER', 'None')}")
                
            # Skip all checks for staff and superusers
            if request.user.is_staff or request.user.is_superuser:
                return self.get_response(request)
                
            # Paths always accessible regardless of status
            always_accessible_paths = [
                '/admin/',
                '/organizations/logout/',
                '/static/',
                '/media/',
                '/legal/',  # Legal documents should be publicly accessible
            ]
            
            # Check if current path is in always accessible paths
            is_always_accessible = any(
                request.path.startswith(path) for path in always_accessible_paths
            )
            
            # If user has organization (should have after registration)
            if hasattr(request.user, 'organization') and request.user.organization:
                org = request.user.organization
                
                # Handle payment/checkout pages specially
                if any(path in request.path for path in [
                    'payments/select-plan', 
                    'payments/checkout', 
                    'register',
                    'organizations/pending-approval'
                ]):
                    request.ui_state = 'payment'
                    return self.get_response(request)
                
                # If organization is pending approval
                if hasattr(org, 'approval_status') and org.approval_status == 'pending':
                    # Set UI state for templates
                    request.ui_state = 'pending_approval'
                    
                    # Allow access to dashboard, organization directory, pilot functionality, and deals
                    pending_allowed_paths = [
                        '/organizations/pending-approval/',
                        '/payments/', # Allow access to payment processing
                        '/organizations/dashboard/', # Allow dashboard access
                        '/organizations/enterprise-dashboard/', # Allow enterprise dashboard
                        '/organizations/startup-dashboard/', # Allow startup dashboard
                        '/organizations/directory/', # Allow browsing organizations
                        '/organizations/profile/', # Allow viewing organization profiles
                        '/pilots/', # Allow full pilots access
                        '/organizations/deals/', # Allow deals access for browsing
                    ]
                    
                    # Block only bid submission for pending users
                    pending_blocked_paths = [
                        '/pilots/bid/',
                    ]
                    
                    is_pending_blocked = any(
                        request.path.startswith(path) for path in pending_blocked_paths
                    )
                    
                    if is_pending_blocked:
                        messages.warning(request, "You must be approved before you can create pilots or submit bids.")
                        return redirect('organizations:pending_approval')
                    
                    is_pending_allowed = any(
                        request.path.startswith(path) for path in pending_allowed_paths
                    )
                    
                    if not is_always_accessible and not is_pending_allowed:
                        # Force redirect to pending approval page
                        return redirect('organizations:pending_approval')
                
                # If organization was rejected
                elif hasattr(org, 'approval_status') and org.approval_status == 'rejected':
                    request.ui_state = 'minimal'
                    
                    if not is_always_accessible:
                        # IMPORTANT: Never redirect to logout directly
                        # Instead show a message and render the current page
                        messages.error(request, "Your account application has been rejected.")
                        # If we're not already on the pending page, redirect there
                        if not request.path.startswith('/organizations/pending-approval/'):
                            return redirect('organizations:pending_approval')
                
                # If organization is approved, handle subscription check
                elif hasattr(org, 'approval_status') and org.approval_status == 'approved':
                    # Check subscription status
                    subscription_exempt_paths = [
                        '/payments/',
                    ]
                    
                    is_subscription_exempt = any(
                        request.path.startswith(path) for path in subscription_exempt_paths
                    ) or is_always_accessible
                    
                    if not is_subscription_exempt:
                        # Only check subscription if the method is available
                        if hasattr(org, 'has_active_subscription') and callable(org.has_active_subscription):
                            if not org.has_active_subscription():
                                request.ui_state = 'subscription'
                                
                                # Redirect from ANY non-payment page to subscription detail
                                if not request.path.startswith('/payments/'):
                                    messages.warning(request, "You need an active subscription to access this page.")
                                    return redirect('payments:subscription_detail')
        else:
            # Unauthenticated - landing UI
            request.ui_state = 'landing'
            
            # Allow unauthenticated access to legal documents
            legal_paths = [
                '/legal/',
                '/static/',
                '/media/',
            ]
            
            # Check if this is a legal document request
            is_legal_accessible = any(
                request.path.startswith(path) for path in legal_paths
            )
            
            # If it's a legal document, allow access without redirecting to login
            if is_legal_accessible:
                pass  # Continue to serve the request
                
        response = self.get_response(request)
        return response