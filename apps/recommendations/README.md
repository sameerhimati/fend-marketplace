# AI/ML Recommendations Foundation

This module provides the foundation for intelligent recommendations in the Fend Marketplace. It includes rule-based systems that can be enhanced with machine learning models in Phase 2.

## Current Features

### Tag Recommendations
- **Industry Tags**: Suggests relevant industry categories based on organization descriptions
- **Skill Tags**: Recommends technical capabilities for startups based on content analysis
- **Rule-based Matching**: Uses keyword analysis and similarity scoring

### Pilot Matching
- **Opportunity Discovery**: Suggests relevant pilot opportunities for startups
- **Compatibility Scoring**: Calculates match scores based on industry overlap and other factors
- **Relevance Ranking**: Orders suggestions by potential success likelihood

### Analytics Foundation
- **Interaction Tracking**: Captures user engagement with recommendations
- **Performance Metrics**: Framework for measuring recommendation effectiveness
- **A/B Testing Ready**: Structure for testing different recommendation strategies

## API Endpoints

### GET `/recommendations/suggest/industry-tags/`
Returns industry tag suggestions for the current user's organization.

**Parameters:**
- `limit` (optional): Number of suggestions to return (default: 8)

**Response:**
```json
{
  "success": true,
  "suggestions": [
    {
      "tag": "AI/ML",
      "confidence": 0.8,
      "reason": "Mentioned in your description",
      "category": "industry"
    }
  ]
}
```

### GET `/recommendations/suggest/skill-tags/`
Returns technical skill suggestions for startups.

### GET `/recommendations/suggest/pilots/`
Returns pilot opportunity suggestions for startups with match scores.

### POST `/recommendations/track/`
Tracks user interactions for ML training data.

### GET `/recommendations/dashboard/`
Returns comprehensive recommendations for organization dashboard.

## Usage

### JavaScript Integration
```javascript
// Load the recommendations engine
const recommendations = new RecommendationEngine();

// Get industry tag suggestions
const tags = await recommendations.getIndustryTagSuggestions(8);

// Render suggestions in UI
await recommendations.renderIndustryTagSuggestions('container-id');

// Track user interactions
recommendations.trackInteraction('industry_tags', 'AI/ML', 'apply');
```

### Template Integration
```html
<!-- Add containers for auto-rendered suggestions -->
<div id="industry-tag-suggestions"></div>
<div id="pilot-suggestions"></div>

<!-- Include the recommendations script -->
<script src="{% static 'js/recommendations.js' %}"></script>
```

## Future ML Integration Points

### Phase 2 Enhancements

1. **Semantic Similarity Models**
   - Replace keyword matching with embedding-based similarity
   - Use BERT or domain-specific language models
   - Implement vector databases for fast similarity search

2. **Collaborative Filtering**
   - Recommend based on similar organization preferences
   - Learn from successful pilot matches
   - Implement user-item matrix factorization

3. **Success Prediction Models**
   - Train models on pilot outcome data
   - Predict match success probability
   - Optimize for business metrics (revenue, satisfaction)

4. **Real-time Learning**
   - Online learning from user interactions
   - A/B testing framework for recommendation strategies
   - Continuous model improvement

5. **Advanced Features**
   - Multi-modal recommendations (text + images + structured data)
   - Explanation generation for recommendations
   - Personalized recommendation timing

### Data Requirements for ML

- **User Interaction Data**: Clicks, applications, dismissals
- **Success Metrics**: Completed pilots, revenue generated, satisfaction scores
- **Content Features**: Organization descriptions, pilot requirements, industry classifications
- **Network Effects**: Connection patterns, collaboration history

### Model Training Pipeline

```python
# Example future ML pipeline
class RecommendationMLPipeline:
    def __init__(self):
        self.feature_extractor = OrganizationFeatureExtractor()
        self.similarity_model = SentenceTransformer('domain-specific-model')
        self.success_predictor = XGBoostRegressor()
    
    def train_models(self, interaction_data, outcome_data):
        # Extract features from organizations and pilots
        features = self.feature_extractor.extract(interaction_data)
        
        # Train similarity embeddings
        self.similarity_model.fit(features['text_content'])
        
        # Train success prediction model
        self.success_predictor.fit(features['structured'], outcome_data['success'])
    
    def predict_recommendations(self, organization):
        # Generate embeddings and predict matches
        pass
```

## Architecture

```
apps/recommendations/
├── __init__.py
├── services.py          # Core recommendation logic
├── views.py            # API endpoints
├── urls.py             # URL routing
├── models.py           # Future: ML model storage
├── analytics.py        # Future: Advanced analytics
└── ml/                 # Future: ML model implementations
    ├── features.py
    ├── models.py
    └── training.py
```

## Configuration

Add to Django settings:
```python
INSTALLED_APPS = [
    ...
    'apps.recommendations',
]

# Future ML settings
RECOMMENDATIONS = {
    'MODEL_BACKEND': 'local',  # 'local', 'api', 'cloud'
    'SIMILARITY_THRESHOLD': 0.7,
    'BATCH_SIZE': 32,
    'UPDATE_FREQUENCY': 'daily',
}
```

## Testing

```bash
# Run recommendation tests
python manage.py test apps.recommendations

# Test API endpoints
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/recommendations/suggest/industry-tags/

# Load test recommendation performance
python manage.py test_recommendation_performance
```

## Monitoring

Future monitoring metrics:
- Click-through rate (CTR) on recommendations
- Conversion rate (recommendations → actions)
- User satisfaction scores
- Model accuracy and precision/recall
- API response times and error rates

## Contributing

When adding new recommendation features:

1. **Start with rule-based logic** in `services.py`
2. **Add API endpoints** in `views.py` and `urls.py`
3. **Include analytics tracking** for future ML training
4. **Document integration points** for ML models
5. **Add JavaScript utilities** for frontend integration

This foundation provides a solid base for Phase 2 ML integration while delivering immediate value through intelligent rule-based recommendations.