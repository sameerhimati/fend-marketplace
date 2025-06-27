from django.http import HttpResponsePermanentRedirect

class LocalHttpRedirectMiddleware:
    """
    Middleware to redirect HTTPS requests to HTTP in local development.
    This is the opposite of HttpsRedirectMiddleware for local dev only.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only redirect if request is secure (HTTPS)
        if request.is_secure():
            # Redirect to HTTP version
            return HttpResponsePermanentRedirect(
                'http://{}{}'.format(request.get_host(), request.get_full_path())
            )
        
        return self.get_response(request)