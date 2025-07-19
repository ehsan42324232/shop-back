from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .social_content_views import (
    SocialPlatformViewSet,
    StoryViewSet,
    PostViewSet,
    ContentSelectionViewSet,
    SocialContentAPIViewSet
)

# Create router for social content APIs
router = DefaultRouter()
router.register(r'platforms', SocialPlatformViewSet, basename='socialplatform')
router.register(r'stories', StoryViewSet, basename='story')
router.register(r'posts', PostViewSet, basename='post')
router.register(r'selections', ContentSelectionViewSet, basename='contentselection')
router.register(r'content', SocialContentAPIViewSet, basename='socialcontent')

urlpatterns = [
    path('social/', include(router.urls)),
]
