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
                
                # FIRST: Check subscription status (regardless of approval)
                if hasattr(org, 'has_active_subscription') and callable(org.has_active_subscription):
                    if not org.has_active_subscription():
                        # Set subscription UI state for ALL pages when subscription is incomplete
                        request.ui_state = 'subscription'
                        
                        # Only redirect from non-payment pages
                        if not request.path.startswith('/payments/'):
                            # Check if user has any subscription at all
                            if hasattr(org, 'subscription') and org.subscription is not None:
                                # User has subscription but it's inactive/expired - go to subscription detail
                                messages.warning(request, "You need an active subscription to access this page.")
                                return redirect('payments:subscription_detail')
                            else:
                                # User has no subscription - go to plan selection
                                messages.warning(request, "Please select a subscription plan to access this page.")
                                return redirect('payments:payment_selection')
                
                # SECOND: If they have active subscription, check approval for specific restrictions
                if hasattr(org, 'approval_status') and org.approval_status == 'pending':
                    # Block only pilot creation and bidding for pending users (they can still access dashboard)
                    pending_blocked_paths = [
                        '/pilots/create/',
                        '/pilots/bid/',
                        '/pilots/publish/',  # Block publishing if that's a separate action
                    ]
                    
                    is_pending_blocked = any(
                        request.path.startswith(path) for path in pending_blocked_paths
                    )
                    
                    if is_pending_blocked:
                        messages.warning(request, "You must be approved before you can create pilots or submit bids.")
                        return redirect('organizations:dashboard')
                
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