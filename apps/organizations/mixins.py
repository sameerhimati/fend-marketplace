from django.shortcuts import redirect
from django.contrib import messages

class OrganizationRequiredMixin:
    """Mixin to ensure user has an organization."""
    
    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'organization') or request.user.organization is None:
            messages.warning(request, "Please complete your organization setup.")
            return redirect('organizations:login')
        return super().dispatch(request, *args, **kwargs)