# Enhanced URLs for Mall Platform
from django.urls import path, include
from . import mall_views, product_instance_views

urlpatterns = [
    # Platform homepage
    path('api/platform/homepage/', mall_views.platform_homepage_data, name='platform_homepage'),
    path('api/platform/store-request/', mall_views.create_store_request, name='create_store_request'),
    path('api/platform/newsletter/', mall_views.newsletter_subscribe, name='newsletter_subscribe'),
    
    # OTP Authentication
    path('api/auth/send-otp/', mall_views.send_otp, name='send_otp'),
    path('api/auth/verify-otp/', mall_views.verify_otp, name='verify_otp'),
    
    # User stores
    path('api/user/stores/', mall_views.user_stores, name='user_stores'),
    
    # Social media integration
    path('api/stores/<uuid:store_id>/sync-social/', mall_views.sync_social_content, name='sync_social_content'),
    
    # Product instances
    path('api/product-instances/', product_instance_views.ProductInstanceViewSet.as_view({'get': 'list', 'post': 'create'})),
    path('api/product-instances/<int:pk>/', product_instance_views.ProductInstanceViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'})),
    path('api/products/<int:product_id>/for-instances/', product_instance_views.product_for_instances, name='product_for_instances'),
]