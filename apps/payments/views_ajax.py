import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


@login_required
@csrf_exempt  
@require_http_methods(["POST"])
def dismiss_subscription_warning(request):
    """
    AJAX endpoint to dismiss subscription warning for current session
    """
    try:
        organization = getattr(request.user, 'organization', None)
        if not organization:
            return JsonResponse({'success': False, 'error': 'No organization found'})
        
        # Set session flag to hide warning for remainder of session
        session_key = f'dismissed_subscription_warning_{organization.id}'
        request.session[session_key] = True
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})