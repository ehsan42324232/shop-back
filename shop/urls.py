# shop/urls.py - Mall Platform URL Configuration
"""
Complete URL configuration for the Mall Platform
Organized according to the product description requirements
"""

from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter

# Import main view modules
from . import views
from .mall_otp_auth_views import *
from .mall_auth_views import *
from .mall_product_views import *
from .mall_social_views import *
from .enhanced_payment_views_v2 import *
from .storefront_views import *
from .analytics_views import *
from .sms_campaign_views import *
from .chat_views import *
from .homepage_api_views import *

# Create router for ViewSets
router = DefaultRouter()

app_name = 'shop'

# Main URL patterns
urlpatterns = [
    
    # ==================== PLATFORM HOMEPAGE ====================
    # Long, fancy, modern homepage with red, blue, white theme
    path('', homepage_api_views.homepage_view, name='homepage'),
    path('api/homepage/features/', homepage_api_views.get_features, name='homepage_features'),
    path('api/homepage/testimonials/', homepage_api_views.get_testimonials, name='testimonials'),
    path('api/homepage/stats/', homepage_api_views.get_platform_stats, name='platform_stats'),
    path('api/homepage/request-demo/', homepage_api_views.request_demo, name='request_demo'),
    path('api/homepage/contact/', homepage_api_views.contact_form, name='contact_form'),
    
    # ==================== MALL AUTHENTICATION (OTP-based) ====================
    # All platform logins use OTP authentication
    path('api/auth/request-otp/', request_otp, name='request_otp'),
    path('api/auth/verify-otp/', verify_otp, name='verify_otp'),
    path('api/auth/logout/', logout_view, name='logout'),
    path('api/auth/refresh/', refresh_token, name='refresh_token'),
    
    # Store owner authentication and management
    path('api/store/register/', register_store_owner, name='register_store_owner'),
    path('api/store/profile/', get_store_profile, name='store_profile'),
    path('api/store/update/', update_store_profile, name='update_store'),
    
    # ==================== PRODUCT SYSTEM (Object-Oriented Hierarchy) ====================
    # Product classes with tree levels and flexible hierarchy
    path('api/product-classes/', ProductClassListCreateView.as_view(), name='product_classes'),
    path('api/product-classes/<int:pk>/', ProductClassDetailView.as_view(), name='product_class_detail'),
    path('api/product-classes/<int:pk>/children/', get_product_class_children, name='product_class_children'),
    
    # Product attributes (predefined: color, description)
    path('api/product-attributes/', ProductAttributeListCreateView.as_view(), name='product_attributes'),
    path('api/product-attributes/<int:pk>/', ProductAttributeDetailView.as_view(), name='product_attribute_detail'),
    path('api/product-attributes/predefined/', create_predefined_attributes, name='create_predefined_attributes'),
    
    # Product instances (only created from leaf nodes)
    path('api/products/', ProductListCreateView.as_view(), name='products'),
    path('api/products/<uuid:pk>/', ProductDetailView.as_view(), name='product_detail'),
    path('api/products/<uuid:pk>/clone/', clone_product_instance, name='clone_product'),
    path('api/products/<uuid:pk>/stock-warning/', check_stock_warning, name='stock_warning'),
    
    # Example product creation (تیشرت یقه گرد نخی)
    path('api/products/create-example/', create_example_tshirt, name='create_example_product'),
    
    # ==================== SOCIAL MEDIA INTEGRATION ====================
    # "Get from social media" button functionality
    path('api/social/extract/', extract_social_content, name='extract_social'),
    path('api/social/telegram/latest/', get_telegram_posts, name='telegram_posts'),
    path('api/social/instagram/latest/', get_instagram_posts, name='instagram_posts'),
    path('api/social/select-content/', select_social_content, name='select_social_content'),
    path('api/social/apply-to-product/', apply_social_to_product, name='apply_social_to_product'),
    
    # ==================== SHOP WEBSITE FEATURES ====================
    
    # Public storefront (customer-facing)
    path('store/<str:domain>/', storefront_home, name='storefront_home'),
    path('store/<str:domain>/products/', storefront_products, name='storefront_products'),
    path('store/<str:domain>/products/<uuid:product_id>/', storefront_product_detail, name='storefront_product_detail'),
    path('store/<str:domain>/categories/', storefront_categories, name='storefront_categories'),
    
    # Product lists (recent, categories, most viewed, recommended)
    path('store/<str:domain>/products/recent/', get_recent_products, name='recent_products'),
    path('store/<str:domain>/products/most-viewed/', get_most_viewed_products, name='most_viewed_products'),
    path('store/<str:domain>/products/recommended/', get_recommended_products, name='recommended_products'),
    path('store/<str:domain>/products/categories/<int:category_id>/', get_category_products, name='category_products'),
    
    # Product search and filtering (by names and categories)
    path('store/<str:domain>/search/', product_search, name='product_search'),
    path('store/<str:domain>/filter/', advanced_filter, name='advanced_filter'),
    
    # Sorting options (recent, most viewed, most purchased, price)
    path('api/products/sort/', sort_products, name='sort_products'),
    
    # ==================== CUSTOMIZATION & THEMES ====================
    # Multiple layout and theme options
    path('api/store/themes/', get_available_themes, name='available_themes'),
    path('api/store/themes/apply/', apply_theme, name='apply_theme'),
    path('api/store/themes/real-time/', real_time_theme_change, name='real_time_theme'),
    
    # Independent domain options
    path('api/store/domain/setup/', setup_custom_domain, name='setup_domain'),
    path('api/store/domain/verify/', verify_custom_domain, name='verify_domain'),
    
    # ==================== E-COMMERCE INTEGRATION ====================
    
    # Shopping cart and checkout
    path('api/cart/', CartView.as_view(), name='cart'),
    path('api/cart/add/', add_to_cart, name='add_to_cart'),
    path('api/cart/update/<int:item_id>/', update_cart_item, name='update_cart_item'),
    path('api/cart/remove/<int:item_id>/', remove_cart_item, name='remove_cart_item'),
    path('api/cart/checkout/', checkout, name='checkout'),
    
    # Customer account creation and management
    path('api/customers/register/', customer_register, name='customer_register'),
    path('api/customers/profile/', customer_profile, name='customer_profile'),
    path('api/customers/addresses/', customer_addresses, name='customer_addresses'),
    
    # Order viewing and management
    path('api/orders/', OrderListCreateView.as_view(), name='orders'),
    path('api/orders/<uuid:pk>/', OrderDetailView.as_view(), name='order_detail'),
    path('api/orders/<uuid:pk>/track/', track_order, name='track_order'),
    
    # ==================== IRANIAN PAYMENT GATEWAYS ====================
    # Integration with major Iranian payment providers
    path('api/payment/gateways/', get_available_payment_gateways, name='payment_gateways'),
    path('api/payment/initiate/', initiate_payment, name='initiate_payment'),
    path('api/payment/verify/', verify_payment, name='verify_payment'),
    path('api/payment/callback/<int:payment_id>/', payment_callback, name='payment_callback'),
    
    # ==================== IRANIAN LOGISTICS ====================
    # Integration with major Iranian logistics providers
    path('api/logistics/providers/', get_logistics_providers, name='logistics_providers'),
    path('api/logistics/calculate/', calculate_shipping_cost, name='calculate_shipping'),
    path('api/logistics/track/<str:tracking_number>/', track_shipment, name='track_shipment'),
    
    # ==================== SMS PROMOTION CAMPAIGNS ====================
    path('api/sms/campaigns/', SMSCampaignListCreateView.as_view(), name='sms_campaigns'),
    path('api/sms/campaigns/<int:pk>/', SMSCampaignDetailView.as_view(), name='sms_campaign_detail'),
    path('api/sms/campaigns/<int:pk>/send/', send_sms_campaign, name='send_sms_campaign'),
    path('api/sms/templates/', sms_templates, name='sms_templates'),
    
    # ==================== ANALYTICS & DASHBOARD ====================
    # Comprehensive dashboards for shop owners
    path('api/analytics/dashboard/', get_store_dashboard, name='analytics_dashboard'),
    path('api/analytics/sales/', get_sales_analytics, name='sales_analytics'),
    path('api/analytics/products/', get_product_analytics, name='product_analytics'),
    path('api/analytics/customers/', get_customer_analytics, name='customer_analytics'),
    
    # Website view statistics
    path('api/analytics/traffic/', get_traffic_analytics, name='traffic_analytics'),
    path('api/analytics/views/', track_page_view, name='track_view'),
    
    # Customer interaction metrics
    path('api/analytics/interactions/', get_interaction_metrics, name='interaction_metrics'),
    
    # ==================== ONLINE CHAT FUNCTIONALITY ====================
    # Sliders and online chat functionality
    path('api/chat/conversations/', chat_conversations, name='chat_conversations'),
    path('api/chat/messages/', chat_messages, name='chat_messages'),
    path('api/chat/send/', send_chat_message, name='send_message'),
    path('api/chat/online-status/', update_online_status, name='online_status'),
    
    # ==================== ADMIN PANEL ACCESS ====================
    # Django admin panel for creating stores, building accounts and managing users
    path('api/admin/stores/', admin_manage_stores, name='admin_stores'),
    path('api/admin/users/', admin_manage_users, name='admin_users'),
    path('api/admin/platform-stats/', admin_platform_stats, name='admin_platform_stats'),
    
    # ==================== MANUAL PRODUCT CREATION ====================
    # Manual product creation interface
    path('api/products/manual-create/', manual_product_creation, name='manual_product_create'),
    path('api/products/bulk-create/', bulk_product_creation, name='bulk_product_create'),
    path('api/products/import/', import_products, name='import_products'),
    path('api/products/export/', export_products, name='export_products'),
    
    # ==================== ADDITIONAL FEATURES ====================
    
    # Contact us and about us sections
    path('contact/', contact_us_view, name='contact_us'),
    path('about/', about_us_view, name='about_us'),
    
    # Pop-up request forms
    path('api/forms/demo-request/', demo_request_form, name='demo_request'),
    path('api/forms/contact/', contact_form_submission, name='contact_form'),
    
    # Health check endpoints
    path('health/', health_check, name='health_check'),
    path('api/health/', api_health_check, name='api_health_check'),
    
    # ==================== ROUTER URLS ====================
    path('api/', include(router.urls)),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Error handlers
handler404 = 'shop.views.custom_404'
handler500 = 'shop.views.custom_500'
