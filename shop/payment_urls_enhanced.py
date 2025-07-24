# shop/payment_urls_enhanced.py
"""
Mall Platform - Enhanced Payment URL Configuration
URL patterns for comprehensive payment system with Iranian gateways
"""
from django.urls import path
from . import enhanced_payment_views_v2

urlpatterns = [
    # Payment Gateway Management
    path('payment/gateways/', enhanced_payment_views_v2.get_available_payment_gateways, name='payment_gateways'),
    
    # Payment Processing
    path('payment/initiate/', enhanced_payment_views_v2.initiate_payment, name='initiate_payment'),
    path('payment/callback/<int:payment_id>/', enhanced_payment_views_v2.payment_callback, name='payment_callback'),
    path('payment/status/<int:payment_id>/', enhanced_payment_views_v2.check_payment_status, name='check_payment_status'),
    
    # Payment History & Management
    path('payment/history/', enhanced_payment_views_v2.get_payment_history, name='payment_history'),
    path('payment/refund/<int:payment_id>/', enhanced_payment_views_v2.refund_payment, name='refund_payment'),
]
