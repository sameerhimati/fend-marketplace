"""
AI/ML Recommendations URL Configuration

AJAX endpoints for intelligent recommendations.
Foundation for future ML-powered features.
"""

from django.urls import path
from . import views

app_name = 'recommendations'

urlpatterns = [
    # Tag recommendation endpoints
    path('suggest/industry-tags/', 
         views.suggest_industry_tags, 
         name='suggest_industry_tags'),
    
    path('suggest/skill-tags/', 
         views.suggest_skill_tags, 
         name='suggest_skill_tags'),
    
    # Pilot matching endpoints
    path('suggest/pilots/', 
         views.suggest_pilots, 
         name='suggest_pilots'),
    
    # Analytics and tracking
    path('track/', 
         views.track_recommendation_interaction, 
         name='track_interaction'),
    
    # Dashboard recommendations
    path('dashboard/', 
         views.recommendation_dashboard, 
         name='dashboard'),
]