from django.http import HttpResponsePermanentRedirect

class HttpsRedirectMiddleware:
    """
    Middleware to redirect all HTTP requests to HTTPS.
    This provides an additional layer of security beyond Nginx redirects.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if the request is secure
        if not request.is_secure():
            # If running behind a proxy that sets the X-Forwarded-Proto header
            if 'HTTP_X_FORWARDED_PROTO' in request.META:
                if request.META['HTTP_X_FORWARDED_PROTO'] != 'https':
                    # Return HTTPS redirect
                    return HttpResponsePermanentRedirect(
                        'https://{}{}'.format(request.get_host(), request.path)
                    )
        
        return self.get_response(request)