from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .recommendation_views import RecommendationViewSet

# Create router for recommendation APIs
router = DefaultRouter()
router.register(r'recommendations', RecommendationViewSet, basename='recommendation')

# Recommendation API URLs
urlpatterns = [
    path('api/', include(router.urls)),
]

app_name = 'recommendations'
