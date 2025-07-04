from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin


class ForcePasswordChangeMiddleware(MiddlewareMixin):
    """Force users to change password if required"""
    
    def process_request(self, request):
        # Skip for anonymous users
        if not request.user.is_authenticated:
            return None
        
        # Skip for superusers and staff
        if request.user.is_superuser or request.user.is_staff:
            return None
        
        # Skip if user doesn't need to change password
        if not request.user.must_change_password:
            return None
        
        # Allow access to password change URLs and logout
        exempt_urls = [
            reverse('users:force_password_change'),
            reverse('users:password_change'),
            reverse('users:password_change_redirect'),
            reverse('organizations:logout'),
            '/admin/logout/',
            '/static/',
            '/media/',
        ]
        
        # Check if current path is exempt
        for exempt_url in exempt_urls:
            if request.path.startswith(exempt_url):
                return None
        
        # Redirect to force password change
        return redirect('users:force_password_change')