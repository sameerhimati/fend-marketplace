class UserOrganizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process the response first
        response = self.get_response(request)
        
        # Only check after response and skip for admin pages or static files
        if (request.user.is_authenticated and 
            not request.path.startswith('/admin/') and
            not request.path.startswith('/static/') and
            not request.path.startswith('/media/')):
            
            # Check for organization integrity
            if not hasattr(request.user, 'organization') or request.user.organization is None:
                # Just log the issue but don't interfere with response
                import logging
                logger = logging.getLogger('django')
                logger.error(f"User {request.user.id} ({request.user.username}) has no organization")
                
                # Don't modify the response - let the view handle it
        
        return response