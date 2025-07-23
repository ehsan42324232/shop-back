from django.urls import path
from . import homepage_api_views

app_name = 'homepage_api'

urlpatterns = [
    # Contact and inquiries
    path('contact/', homepage_api_views.ContactRequestCreateView.as_view(), name='contact-create'),
    path('quick-contact/', homepage_api_views.quick_contact, name='quick-contact'),
    
    # Platform information
    path('settings/', homepage_api_views.PlatformSettingsView.as_view(), name='settings'),
    path('stats/', homepage_api_views.PlatformStatsView.as_view(), name='stats'),
    path('homepage-data/', homepage_api_views.homepage_data, name='homepage-data'),
    
    # Newsletter
    path('newsletter/', homepage_api_views.NewsletterSubscribeView.as_view(), name='newsletter-subscribe'),
    
    # FAQ
    path('faq/', homepage_api_views.FAQListView.as_view(), name='faq-list'),
    
    # Health check
    path('health/', homepage_api_views.health_check, name='health-check'),
]
