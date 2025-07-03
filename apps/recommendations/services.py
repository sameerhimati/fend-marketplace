"""
AI/ML Recommendations Service - Foundation Layer

This module provides the foundation for intelligent recommendations including:
- Industry tag suggestions
- Skill/expertise recommendations  
- Pilot matching suggestions
- Partner recommendations

Future integration points for ML models, embeddings, and advanced matching algorithms.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
from django.db.models import Q, Count
from apps.organizations.models import Organization
from apps.pilots.models import Pilot


class TagRecommendationService:
    """
    Foundation service for intelligent tag recommendations.
    Currently uses rule-based approaches with hooks for future ML integration.
    """
    
    # Curated industry tags for initial recommendations
    INDUSTRY_TAGS = [
        'AI/ML', 'FinTech', 'SaaS', 'Healthcare', 'EdTech', 'PropTech', 
        'CleanTech', 'Cybersecurity', 'DevOps', 'Cloud Infrastructure',
        'Data Analytics', 'IoT', 'Blockchain', 'E-commerce', 'MarTech',
        'HRTech', 'LegalTech', 'InsurTech', 'Supply Chain', 'Logistics',
        'Manufacturing', 'Retail', 'Media', 'Gaming', 'Mobile Apps'
    ]
    
    # Common technical skills for startups
    TECHNICAL_SKILLS = [
        'Python', 'JavaScript', 'React', 'Node.js', 'AWS', 'Docker',
        'Kubernetes', 'Machine Learning', 'Data Science', 'APIs',
        'Microservices', 'Database Design', 'Mobile Development',
        'UI/UX Design', 'Product Management', 'DevOps', 'Security'
    ]
    
    @classmethod
    def suggest_industry_tags(cls, organization: Organization, limit: int = 8) -> List[Dict[str, Any]]:
        """
        Suggest relevant industry tags for an organization.
        
        Future: Replace with ML model trained on organization descriptions,
        website content, and industry classifications.
        """
        suggestions = []
        
        # Analyze organization description and name for keywords
        text_content = f"{organization.name} {organization.description or ''}".lower()
        
        # Rule-based matching (foundation for ML features)
        for tag in cls.INDUSTRY_TAGS:
            relevance_score = cls._calculate_tag_relevance(text_content, tag)
            if relevance_score > 0:
                suggestions.append({
                    'tag': tag,
                    'confidence': relevance_score,
                    'reason': cls._get_match_reason(text_content, tag),
                    'category': 'industry'
                })
        
        # Add popular tags in similar organizations
        similar_tags = cls._get_similar_organization_tags(organization, limit=3)
        suggestions.extend(similar_tags)
        
        # Sort by confidence and return top suggestions
        suggestions.sort(key=lambda x: x['confidence'], reverse=True)
        return suggestions[:limit]
    
    @classmethod
    def suggest_skill_tags(cls, organization: Organization, limit: int = 6) -> List[Dict[str, Any]]:
        """
        Suggest technical skill tags for organizations.
        
        Future: Analyze pilot descriptions, requirements, and past work
        to suggest relevant technical capabilities.
        """
        if organization.type != 'startup':
            return []
        
        suggestions = []
        
        # Analyze all pilot content from this organization
        pilot_content = ""
        for pilot in organization.pilots.all():
            pilot_content += f" {pilot.title} {pilot.description}"
        
        text_content = f"{organization.description or ''} {pilot_content}".lower()
        
        for skill in cls.TECHNICAL_SKILLS:
            relevance_score = cls._calculate_tag_relevance(text_content, skill)
            if relevance_score > 0:
                suggestions.append({
                    'tag': skill,
                    'confidence': relevance_score,
                    'reason': cls._get_match_reason(text_content, skill),
                    'category': 'skill'
                })
        
        suggestions.sort(key=lambda x: x['confidence'], reverse=True)
        return suggestions[:limit]
    
    @classmethod
    def _calculate_tag_relevance(cls, text: str, tag: str) -> float:
        """
        Calculate relevance score between text content and a tag.
        
        Future: Replace with semantic similarity using embeddings,
        BERT, or specialized domain models.
        """
        tag_lower = tag.lower()
        tag_parts = re.split(r'[/\s]+', tag_lower)
        
        relevance = 0.0
        
        # Exact tag match
        if tag_lower in text:
            relevance += 1.0
        
        # Partial matches for composite tags like "AI/ML"
        for part in tag_parts:
            if len(part) > 2 and part in text:
                relevance += 0.5
        
        # Related keyword matching (basic semantic matching)
        keyword_map = {
            'ai/ml': ['artificial intelligence', 'machine learning', 'neural', 'deep learning'],
            'fintech': ['financial', 'banking', 'payments', 'crypto', 'trading'],
            'saas': ['software as a service', 'subscription', 'cloud software'],
            'healthcare': ['medical', 'health', 'patient', 'clinical', 'pharma'],
            'edtech': ['education', 'learning', 'student', 'teaching', 'course'],
        }
        
        related_keywords = keyword_map.get(tag_lower, [])
        for keyword in related_keywords:
            if keyword in text:
                relevance += 0.3
        
        return min(relevance, 1.0)  # Cap at 1.0
    
    @classmethod
    def _get_match_reason(cls, text: str, tag: str) -> str:
        """
        Provide human-readable reason for tag suggestion.
        
        Future: Generate explanations using language models.
        """
        tag_lower = tag.lower()
        
        if tag_lower in text:
            return f"Mentioned in your description"
        
        # Check for related keywords
        keyword_map = {
            'ai/ml': ['artificial intelligence', 'machine learning'],
            'fintech': ['financial', 'payments'],
            'healthcare': ['medical', 'health'],
        }
        
        for keyword in keyword_map.get(tag_lower, []):
            if keyword in text:
                return f"Related to '{keyword}' in your content"
        
        return "Popular in similar companies"
    
    @classmethod
    def _get_similar_organization_tags(cls, organization: Organization, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Find tags used by similar organizations.
        
        Future: Use ML clustering, embeddings, or collaborative filtering
        to find truly similar organizations.
        """
        suggestions = []
        
        # Find organizations with similar size or industry (basic similarity)
        similar_orgs = Organization.objects.filter(
            type=organization.type,
            approval_status='approved'
        ).exclude(id=organization.id)
        
        # Collect all industry tags from similar organizations
        all_tags = []
        for org in similar_orgs[:20]:  # Sample subset for performance
            if org.industry_tags:
                all_tags.extend(org.industry_tags)
        
        # Find most common tags
        tag_counts = Counter(all_tags)
        popular_tags = tag_counts.most_common(limit)
        
        for tag, count in popular_tags:
            # Skip if organization already has this tag
            if tag not in (organization.industry_tags or []):
                suggestions.append({
                    'tag': tag,
                    'confidence': min(0.6, count / 10),  # Scale confidence
                    'reason': f"Used by {count} similar companies",
                    'category': 'industry'
                })
        
        return suggestions


class PilotMatchingService:
    """
    Foundation service for intelligent pilot-startup matching.
    
    Future: Implement ML models for semantic matching, success prediction,
    and compatibility scoring.
    """
    
    @classmethod
    def suggest_pilots_for_startup(cls, startup: Organization, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Suggest relevant pilot opportunities for a startup.
        
        Future: Use ML models to predict match success, semantic similarity,
        and compatibility scores.
        """
        if startup.type != 'startup':
            return []
        
        # Get available pilots
        available_pilots = Pilot.objects.filter(
            status='published',
            is_private=False,
            organization__approval_status='approved'
        ).exclude(
            bids__startup=startup
        ).exclude(
            bids__status__in=['approved', 'live', 'completion_pending', 'completed']
        )
        
        pilot_scores = []
        startup_tags = set(startup.industry_tags or [])
        
        for pilot in available_pilots[:50]:  # Limit for performance
            score = cls._calculate_pilot_match_score(startup, pilot, startup_tags)
            if score > 0.1:  # Only include meaningful matches
                pilot_scores.append({
                    'pilot': pilot,
                    'match_score': score,
                    'reasons': cls._get_match_reasons(startup, pilot, startup_tags)
                })
        
        # Sort by match score
        pilot_scores.sort(key=lambda x: x['match_score'], reverse=True)
        return pilot_scores[:limit]
    
    @classmethod
    def _calculate_pilot_match_score(cls, startup: Organization, pilot: Pilot, startup_tags: set) -> float:
        """
        Calculate compatibility score between startup and pilot.
        
        Future: Use ML model trained on successful pilot outcomes,
        semantic embeddings, and multi-factor compatibility analysis.
        """
        score = 0.0
        
        # Industry tag overlap
        pilot_text = f"{pilot.title} {pilot.description}".lower()
        
        for tag in startup_tags:
            if tag.lower() in pilot_text:
                score += 0.3
        
        # Size compatibility (heuristic)
        if startup.employee_count and pilot.organization.employee_count:
            # Prefer some size difference for pilot relationships
            score += 0.2
        
        # Recency bonus
        from django.utils import timezone
        days_old = (timezone.now() - pilot.created_at).days
        if days_old < 7:
            score += 0.2
        elif days_old < 30:
            score += 0.1
        
        return min(score, 1.0)
    
    @classmethod
    def _get_match_reasons(cls, startup: Organization, pilot: Pilot, startup_tags: set) -> List[str]:
        """
        Generate human-readable reasons for pilot match.
        
        Future: Use NLP models to generate detailed explanations.
        """
        reasons = []
        
        # Check tag matches
        pilot_text = f"{pilot.title} {pilot.description}".lower()
        matched_tags = [tag for tag in startup_tags if tag.lower() in pilot_text]
        
        if matched_tags:
            reasons.append(f"Matches your expertise in {', '.join(matched_tags[:2])}")
        
        # Check recency
        from django.utils import timezone
        days_old = (timezone.now() - pilot.created_at).days
        if days_old < 7:
            reasons.append("Recently posted opportunity")
        
        # Industry alignment
        if pilot.organization.type == 'enterprise':
            reasons.append("Enterprise client seeking innovation")
        
        return reasons[:3]  # Limit to top 3 reasons


class RecommendationAnalytics:
    """
    Analytics service for recommendation system performance.
    
    Future: Track recommendation click-through rates, conversion rates,
    and model performance metrics for continuous improvement.
    """
    
    @classmethod
    def track_recommendation_interaction(cls, user_id: int, recommendation_type: str, 
                                       item_id: str, action: str, metadata: Dict = None):
        """
        Track user interactions with recommendations for ML training.
        
        Future: Store in dedicated analytics database, feed into model
        training pipelines, and A/B testing frameworks.
        """
        # TODO: Implement analytics tracking
        # This would typically store interaction data for model training
        pass
    
    @classmethod
    def get_recommendation_performance(cls, recommendation_type: str, 
                                     timeframe_days: int = 30) -> Dict[str, float]:
        """
        Get performance metrics for recommendation system.
        
        Future: Calculate precision, recall, click-through rates,
        and business impact metrics.
        """
        # TODO: Implement performance analytics
        return {
            'click_through_rate': 0.0,
            'conversion_rate': 0.0,
            'user_satisfaction': 0.0
        }