/**
 * AI/ML Recommendations JavaScript Utilities
 * 
 * Foundation for intelligent recommendation features.
 * Future: Integrate with ML model APIs and advanced UI components.
 */

class RecommendationEngine {
    constructor() {
        this.baseUrl = '/recommendations/';
        this.csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
                         document.querySelector('meta[name=csrf-token]')?.content;
    }

    /**
     * Get CSRF token for requests
     */
    getCSRFToken() {
        return this.csrfToken || 
               document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
               '';
    }

    /**
     * Make authenticated request to recommendations API
     */
    async makeRequest(endpoint, options = {}) {
        const defaultOptions = {
            headers: {
                'X-CSRFToken': this.getCSRFToken(),
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin'
        };

        const response = await fetch(this.baseUrl + endpoint, {
            ...defaultOptions,
            ...options,
            headers: { ...defaultOptions.headers, ...options.headers }
        });

        if (!response.ok) {
            throw new Error(`Recommendation API error: ${response.status}`);
        }

        return response.json();
    }

    /**
     * Get industry tag suggestions
     */
    async getIndustryTagSuggestions(limit = 8) {
        try {
            const response = await this.makeRequest(`suggest/industry-tags/?limit=${limit}`);
            return response.suggestions || [];
        } catch (error) {
            console.error('Failed to get industry tag suggestions:', error);
            return [];
        }
    }

    /**
     * Get technical skill tag suggestions (for startups)
     */
    async getSkillTagSuggestions(limit = 6) {
        try {
            const response = await this.makeRequest(`suggest/skill-tags/?limit=${limit}`);
            return response.suggestions || [];
        } catch (error) {
            console.error('Failed to get skill tag suggestions:', error);
            return [];
        }
    }

    /**
     * Get pilot opportunity suggestions (for startups)
     */
    async getPilotSuggestions(limit = 5) {
        try {
            const response = await this.makeRequest(`suggest/pilots/?limit=${limit}`);
            return response.suggestions || [];
        } catch (error) {
            console.error('Failed to get pilot suggestions:', error);
            return [];
        }
    }

    /**
     * Track user interaction with recommendations (for ML training)
     */
    async trackInteraction(type, itemId, action, metadata = {}) {
        try {
            await this.makeRequest('track/', {
                method: 'POST',
                body: JSON.stringify({
                    type: type,
                    item_id: itemId,
                    action: action,
                    metadata: metadata
                })
            });
        } catch (error) {
            console.error('Failed to track recommendation interaction:', error);
        }
    }

    /**
     * Get comprehensive recommendations for dashboard
     */
    async getDashboardRecommendations() {
        try {
            const response = await this.makeRequest('dashboard/');
            return response.dashboard || {};
        } catch (error) {
            console.error('Failed to get dashboard recommendations:', error);
            return {};
        }
    }

    /**
     * Render industry tag suggestions in a container
     */
    async renderIndustryTagSuggestions(containerId, options = {}) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const suggestions = await this.getIndustryTagSuggestions(options.limit);
        if (suggestions.length === 0) {
            container.style.display = 'none';
            return;
        }

        container.innerHTML = `
            <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                <div class="flex items-start">
                    <div class="flex-shrink-0">
                        <svg class="h-5 w-5 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
                        </svg>
                    </div>
                    <div class="ml-3 flex-1">
                        <h4 class="text-sm font-medium text-blue-800 mb-2">
                            AI-Suggested Industry Tags
                        </h4>
                        <p class="text-sm text-blue-700 mb-3">
                            Based on your profile, we recommend these industry tags to improve discoverability:
                        </p>
                        <div class="flex flex-wrap gap-2 mb-3">
                            ${suggestions.slice(0, options.limit || 6).map(suggestion => `
                                <button onclick="addSuggestedTag('${suggestion.tag}', '${suggestion.category}')"
                                        class="inline-flex items-center px-2.5 py-1.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 hover:bg-blue-200 transition-colors"
                                        title="${suggestion.reason}">
                                    ${suggestion.tag}
                                    <span class="ml-1 text-blue-600">+</span>
                                </button>
                            `).join('')}
                        </div>
                        <div class="text-xs text-blue-600">
                            <button onclick="this.closest('.bg-blue-50').style.display='none'"
                                    class="text-blue-600 hover:text-blue-800">
                                Maybe later
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render pilot suggestions for startups
     */
    async renderPilotSuggestions(containerId, options = {}) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const suggestions = await this.getPilotSuggestions(options.limit);
        if (suggestions.length === 0) {
            container.style.display = 'none';
            return;
        }

        container.innerHTML = `
            <div class="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
                <div class="flex items-start">
                    <div class="flex-shrink-0">
                        <svg class="h-5 w-5 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                        </svg>
                    </div>
                    <div class="ml-3 flex-1">
                        <h4 class="text-sm font-medium text-green-800 mb-2">
                            Recommended Pilot Opportunities
                        </h4>
                        <div class="space-y-3">
                            ${suggestions.slice(0, options.limit || 3).map(suggestion => `
                                <div class="border border-green-200 rounded-md p-3 bg-white">
                                    <h5 class="font-medium text-gray-900 text-sm mb-1">
                                        <a href="${suggestion.url}" class="text-green-700 hover:text-green-900">
                                            ${suggestion.pilot_title}
                                        </a>
                                    </h5>
                                    <p class="text-xs text-gray-600 mb-2">
                                        ${suggestion.pilot_description}
                                    </p>
                                    <div class="flex items-center justify-between text-xs">
                                        <span class="text-gray-500">by ${suggestion.organization_name}</span>
                                        <span class="text-green-600 font-medium">
                                            ${Math.round(suggestion.match_score * 100)}% match
                                        </span>
                                    </div>
                                    ${suggestion.reasons.length > 0 ? `
                                        <div class="mt-2 text-xs text-green-700">
                                            ${suggestion.reasons[0]}
                                        </div>
                                    ` : ''}
                                </div>
                            `).join('')}
                        </div>
                        <div class="mt-3 text-xs">
                            <a href="/pilots/" class="text-green-600 hover:text-green-800 font-medium">
                                View all opportunities →
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
}

// Global instance
const recommendations = new RecommendationEngine();

/**
 * Helper function to add suggested tags (implement in your tag management code)
 */
function addSuggestedTag(tag, category) {
    // Track the interaction
    recommendations.trackInteraction('industry_tags', tag, 'apply', { category });
    
    // TODO: Implement actual tag addition logic
    console.log('Adding suggested tag:', tag, 'category:', category);
    
    // Example: Add to form field or trigger tag addition
    // This would be customized based on your existing tag management UI
}

/**
 * Initialize recommendations on page load
 */
document.addEventListener('DOMContentLoaded', function() {
    // Auto-render recommendations if containers exist
    if (document.getElementById('industry-tag-suggestions')) {
        recommendations.renderIndustryTagSuggestions('industry-tag-suggestions');
    }
    
    if (document.getElementById('pilot-suggestions')) {
        recommendations.renderPilotSuggestions('pilot-suggestions');
    }
});