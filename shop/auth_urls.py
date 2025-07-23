from django.urls import path
from . import auth_views

app_name = 'auth_api'

urlpatterns = [
    # OTP Authentication
    path('send-otp/', auth_views.SendOTPView.as_view(), name='send-otp'),
    path('verify-otp/', auth_views.VerifyOTPView.as_view(), name='verify-otp'),
    
    # User Management
    path('register/', auth_views.RegisterView.as_view(), name='register'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Profile Management
    path('profile/', auth_views.ProfileView.as_view(), name='profile'),
    path('status/', auth_views.auth_status, name='auth-status'),
    path('change-password/', auth_views.change_password, name='change-password'),
]
