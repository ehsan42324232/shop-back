from django.urls import path, include
from . import mall_auth_views

# Mall Platform Authentication URLs
mall_auth_patterns = [
    # OTP Authentication
    path('send-otp/', mall_auth_views.SendOTPView.as_view(), name='send_otp'),
    path('verify-otp/', mall_auth_views.VerifyOTPView.as_view(), name='verify_otp'),
    
    # Store Creation Requests
    path('request-store/', mall_auth_views.request_store_creation, name='request_store'),
    
    # Public Stats
    path('stats/', mall_auth_views.platform_stats, name='platform_stats'),
]

urlpatterns = [
    # Include existing URLs
    path('', include('shop.urls')),
    
    # Mall Platform specific authentication
    path('api/mall-auth/', include(mall_auth_patterns)),
    
    # Authentication endpoints
    path('api/auth/', include('shop.auth_urls')),
    
    # Product management
    path('api/products/', include('shop.product_urls')),
    
    # Store management
    path('api/store/', include('shop.store_management_urls')),
    
    # Storefront public APIs
    path('api/storefront/', include('shop.storefront_urls')),
    
    # Analytics
    path('api/analytics/', include('shop.analytics_urls')),
    
    # Social content integration
    path('api/social/', include('shop.social_content_urls')),
    
    # Homepage management
    path('api/homepage/', include('shop.homepage_urls')),
    
    # Chat system
    path('api/chat/', include('shop.chat_urls')),
]
