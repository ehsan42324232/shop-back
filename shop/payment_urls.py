# shop/payment_urls.py
from django.urls import path, include
from . import enhanced_payment_views

app_name = 'payments'

urlpatterns = [
    # Payment initiation and processing
    path('initiate/', enhanced_payment_views.initiate_payment, name='initiate_payment'),
    path('verify/', enhanced_payment_views.verify_payment, name='verify_payment'),
    path('status/<uuid:payment_id>/', enhanced_payment_views.payment_status, name='payment_status'),
    
    # Payment management
    path('user/payments/', enhanced_payment_views.user_payments, name='user_payments'),
    path('retry/<uuid:payment_id>/', enhanced_payment_views.retry_payment, name='retry_payment'),
    path('receipt/<uuid:payment_id>/', enhanced_payment_views.payment_receipt, name='payment_receipt'),
    
    # Refunds
    path('refund/<uuid:payment_id>/', enhanced_payment_views.request_refund, name='request_refund'),
    
    # Gateway information
    path('gateways/', enhanced_payment_views.available_gateways, name='available_gateways'),
    path('calculate-fee/', enhanced_payment_views.calculate_gateway_fee, name='calculate_fee'),
    
    # Admin endpoints
    path('admin/payments/', enhanced_payment_views.admin_payments_list, name='admin_payments_list'),
    path('admin/verify/<uuid:payment_id>/', enhanced_payment_views.admin_manual_verify, name='admin_manual_verify'),
]
