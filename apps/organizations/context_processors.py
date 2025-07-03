from .models import UserOnboardingProgress


def onboarding_suggestions(request):
    """
    Add subtle onboarding suggestions to all authenticated users.
    Returns None if user doesn't want suggestions or has completed onboarding.
    """
    if not request.user.is_authenticated:
        return {}
    
    if not hasattr(request.user, 'organization') or not request.user.organization:
        return {}
    
    # Get user's onboarding progress
    progress = UserOnboardingProgress.get_or_create_for_user(request.user)
    
    # Get next suggestion (returns None if onboarding disabled or complete)
    next_suggestion = progress.get_next_suggestion()
    
    return {
        'onboarding_progress': progress,
        'onboarding_suggestion': next_suggestion,
        'onboarding_completion': progress.get_completion_percentage(),
        'show_progress_bar': progress.should_show_progress_bar()
    }