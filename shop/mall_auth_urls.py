# Mall Platform URL Patterns
from django.urls import path, include
from . import mall_otp_auth_views as auth_views

# Mall authentication URL patterns
mall_auth_patterns = [
    # OTP Authentication
    path('request-otp/', auth_views.request_otp, name='mall_request_otp'),
    path('verify-otp/', auth_views.verify_otp, name='mall_verify_otp'),
    
    # Registration
    path('register-store-owner/', auth_views.register_store_owner, name='mall_register_store_owner'),
    path('register-customer/', auth_views.register_customer, name='mall_register_customer'),
    
    # Profile Management
    path('profile/', auth_views.get_profile, name='mall_get_profile'),
    path('profile/update/', auth_views.update_profile, name='mall_update_profile'),
    
    # Token Management
    path('refresh-token/', auth_views.refresh_token, name='mall_refresh_token'),
    path('logout/', auth_views.logout, name='mall_logout'),
]

# Main URL patterns for Mall platform
urlpatterns = [
    # Authentication endpoints
    path('auth/', include(mall_auth_patterns)),
]
