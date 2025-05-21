class UserOrganizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_superuser:
            # Check for organization integrity
            if not hasattr(request.user, 'organization') or request.user.organization is None:
                from django.contrib import messages
                messages.error(request, "Your account needs organization data. Please contact support.")
                
                # Log the issue for admins to investigate
                import logging
                logger = logging.getLogger('django')
                logger.error(f"User {request.user.id} ({request.user.username}) has no organization")
                
                # Don't redirect here - defensive checks in views will handle that
        
        return self.get_response(request)