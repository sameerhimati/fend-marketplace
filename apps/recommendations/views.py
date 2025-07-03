"""
AI/ML Recommendations Views

AJAX endpoints for getting intelligent recommendations.
Foundation for future ML-powered features.
"""

import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .services import TagRecommendationService, PilotMatchingService, RecommendationAnalytics


@login_required
@csrf_exempt
@require_http_methods(["GET"])
def suggest_industry_tags(request):
    """
    Get AI-powered industry tag suggestions for current user's organization.
    
    Future: Integrate with ML models for semantic tag suggestions.
    """
    try:
        organization = getattr(request.user, 'organization', None)
        if not organization:
            return JsonResponse({'success': False, 'error': 'No organization found'})
        
        # Get tag suggestions
        suggestions = TagRecommendationService.suggest_industry_tags(
            organization, 
            limit=int(request.GET.get('limit', 8))
        )
        
        # Track analytics
        RecommendationAnalytics.track_recommendation_interaction(
            user_id=request.user.id,
            recommendation_type='industry_tags',
            item_id=str(organization.id),
            action='request',
            metadata={'limit': len(suggestions)}
        )
        
        return JsonResponse({
            'success': True,
            'suggestions': suggestions,
            'organization_type': organization.type
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
@require_http_methods(["GET"])
def suggest_skill_tags(request):
    """
    Get AI-powered technical skill tag suggestions for startups.
    
    Future: Analyze codebase, past projects, and capabilities for suggestions.
    """
    try:
        organization = getattr(request.user, 'organization', None)
        if not organization:
            return JsonResponse({'success': False, 'error': 'No organization found'})
        
        if organization.type != 'startup':
            return JsonResponse({
                'success': True,
                'suggestions': [],
                'message': 'Skill tags are primarily for startups'
            })
        
        # Get skill suggestions
        suggestions = TagRecommendationService.suggest_skill_tags(
            organization,
            limit=int(request.GET.get('limit', 6))
        )
        
        # Track analytics
        RecommendationAnalytics.track_recommendation_interaction(
            user_id=request.user.id,
            recommendation_type='skill_tags',
            item_id=str(organization.id),
            action='request',
            metadata={'limit': len(suggestions)}
        )
        
        return JsonResponse({
            'success': True,
            'suggestions': suggestions
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
@require_http_methods(["GET"])
def suggest_pilots(request):
    """
    Get AI-powered pilot opportunity suggestions for startups.
    
    Future: Use ML models for semantic matching and success prediction.
    """
    try:
        organization = getattr(request.user, 'organization', None)
        if not organization:
            return JsonResponse({'success': False, 'error': 'No organization found'})
        
        if organization.type != 'startup':
            return JsonResponse({
                'success': True,
                'suggestions': [],
                'message': 'Pilot suggestions are for startups'
            })
        
        # Get pilot suggestions
        suggestions = PilotMatchingService.suggest_pilots_for_startup(
            organization,
            limit=int(request.GET.get('limit', 5))
        )
        
        # Format for JSON response
        formatted_suggestions = []
        for suggestion in suggestions:
            pilot = suggestion['pilot']
            formatted_suggestions.append({
                'pilot_id': pilot.id,
                'pilot_title': pilot.title,
                'pilot_description': pilot.description[:200] + '...' if len(pilot.description) > 200 else pilot.description,
                'organization_name': pilot.organization.name,
                'match_score': suggestion['match_score'],
                'reasons': suggestion['reasons'],
                'url': f'/pilots/{pilot.id}/',  # Update with actual URL pattern
                'created_days_ago': (pilot.created_at.date() - pilot.created_at.date()).days
            })
        
        # Track analytics
        RecommendationAnalytics.track_recommendation_interaction(
            user_id=request.user.id,
            recommendation_type='pilot_matches',
            item_id=str(organization.id),
            action='request',
            metadata={'suggestions_count': len(formatted_suggestions)}
        )
        
        return JsonResponse({
            'success': True,
            'suggestions': formatted_suggestions
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def track_recommendation_interaction(request):
    """
    Track user interactions with recommendations for ML training.
    
    Future: Feed into recommendation model training and A/B testing.
    """
    try:
        data = json.loads(request.body)
        
        RecommendationAnalytics.track_recommendation_interaction(
            user_id=request.user.id,
            recommendation_type=data.get('type'),
            item_id=data.get('item_id'),
            action=data.get('action'),  # 'click', 'dismiss', 'apply', etc.
            metadata=data.get('metadata', {})
        )
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
@require_http_methods(["GET"])
def recommendation_dashboard(request):
    """
    Get comprehensive recommendations for organization dashboard.
    
    Future: Personalized AI-powered dashboard with multiple recommendation types.
    """
    try:
        organization = getattr(request.user, 'organization', None)
        if not organization:
            return JsonResponse({'success': False, 'error': 'No organization found'})
        
        dashboard_data = {
            'organization_type': organization.type,
            'has_industry_tags': bool(organization.industry_tags),
            'tag_count': len(organization.industry_tags or [])
        }
        
        # Industry tag suggestions (if needed)
        if len(organization.industry_tags or []) < 3:
            dashboard_data['industry_suggestions'] = TagRecommendationService.suggest_industry_tags(
                organization, limit=5
            )
        
        # Skill tag suggestions for startups
        if organization.type == 'startup':
            dashboard_data['skill_suggestions'] = TagRecommendationService.suggest_skill_tags(
                organization, limit=4
            )
            
            # Pilot suggestions
            dashboard_data['pilot_suggestions'] = PilotMatchingService.suggest_pilots_for_startup(
                organization, limit=3
            )
        
        return JsonResponse({
            'success': True,
            'dashboard': dashboard_data
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})