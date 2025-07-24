"""
Enhanced Social Media URLs for Mall Platform
URL patterns for social media content fetching and management
"""

from django.urls import path
from .enhanced_social_views import (
    SocialMediaContentFetchView,
    SocialMediaChannelValidationView,
    SocialMediaContentHistoryView,
    SocialMediaContentPreviewView
)

app_name = 'enhanced_social'

urlpatterns = [
    # Social media content fetching
    path('fetch-content/', 
         SocialMediaContentFetchView.as_view(), 
         name='fetch_content'),
    
    # Channel/account validation
    path('validate-channels/', 
         SocialMediaChannelValidationView.as_view(), 
         name='validate_channels'),
    
    # Content preview
    path('preview/', 
         SocialMediaContentPreviewView.as_view(), 
         name='preview'),
    
    # User's fetch history
    path('history/', 
         SocialMediaContentHistoryView.as_view(), 
         name='history'),
]