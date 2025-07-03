import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import UserOnboardingProgress


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def dismiss_suggestion(request):
    """
    AJAX endpoint to dismiss a specific onboarding suggestion.
    User can dismiss individual suggestions without disabling all onboarding.
    """
    try:
        data = json.loads(request.body)
        suggestion_id = data.get('suggestion_id')
        
        if not suggestion_id:
            return JsonResponse({'success': False, 'error': 'Missing suggestion_id'})
        
        # Get or create user's onboarding progress
        progress = UserOnboardingProgress.get_or_create_for_user(request.user)
        
        # Dismiss the specific suggestion
        progress.dismiss_suggestion(suggestion_id)
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required  
@csrf_exempt
@require_http_methods(["POST"])
def disable_onboarding(request):
    """
    AJAX endpoint to completely disable onboarding suggestions for the user.
    This is a more permanent action than dismissing individual suggestions.
    """
    try:
        # Get or create user's onboarding progress
        progress = UserOnboardingProgress.get_or_create_for_user(request.user)
        
        # Disable all onboarding
        progress.disable_all_onboarding()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt  
@require_http_methods(["POST"])
def update_milestone(request):
    """
    AJAX endpoint to manually update onboarding milestones.
    This can be called when users complete certain actions.
    """
    try:
        data = json.loads(request.body)
        milestone = data.get('milestone')
        completed = data.get('completed', True)
        
        if not milestone:
            return JsonResponse({'success': False, 'error': 'Missing milestone'})
        
        # Get or create user's onboarding progress
        progress = UserOnboardingProgress.get_or_create_for_user(request.user)
        
        # Update the milestone
        progress.update_milestone(milestone, completed)
        
        return JsonResponse({
            'success': True,
            'completion_percentage': progress.get_completion_percentage()
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def dismiss_progress_widget(request):
    """
    AJAX endpoint to dismiss the compact progress widget for current session.
    This hides the widget without permanently disabling onboarding.
    """
    try:
        # Set session flag to hide progress widget for remainder of session
        request.session['dismissed_progress_widget'] = True
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def dismiss_session_progress(request):
    """
    AJAX endpoint to dismiss the session progress bar for current session.
    This hides the dashboard progress bar but keeps corner widget.
    """
    try:
        # Set session flag to hide session progress bar for remainder of session
        request.session['dismissed_session_progress'] = True
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})