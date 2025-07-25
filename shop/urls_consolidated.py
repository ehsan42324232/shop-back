"""
Mall Platform - Consolidated URL Configuration
Combines all URL patterns from multiple files into a single, organized file.
"""

from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Import views from different modules
from . import (
    views, authentication, storefront_views, import_views, analytics_views,
    search_views, order_views, comment_views, cart_views, customer_views
)

# Mall-specific views
from . import (
    mall_auth_views, mall_otp_auth_views, mall_product_views, mall_social_views
)

# Enhanced feature views
try:
    from . import enhanced_payment_views_v2 as payment_views
except ImportError:
    from . import payment_views

try:
    from . import logistics_views_v2 as logistics_views
except ImportError:
    from . import logistics_views

from . import (
    enhanced_social_views,
    sms_campaign_views,
    homepage_api_views,
    store_management_views,
    recommendation_views,
    realtime_chat_views
)

# API URL Patterns
api_v1_patterns = [
    # ==================== PLATFORM HOMEPAGE APIs ====================
    path('homepage/features/', homepage_api_views.HomepageFeatureViewSet.as_view({'get': 'list'}), name='homepage_features'),
    path('homepage/hero-sections/', homepage_api_views.HeroSectionViewSet.as_view({'get': 'list'}), name='hero_sections'),
    path('homepage/call-to-actions/', homepage_api_views.CallToActionViewSet.as_view({'get': 'list'}), name='cta_sections'),
    path('homepage/testimonials/', homepage_api_views.TestimonialViewSet.as_view({'get': 'list'}), name='testimonials'),
    path('homepage/request-demo/', homepage_api_views.request_demo, name='request_demo'),
    path('homepage/contact-form/', homepage_api_views.contact_form_submission, name='contact_form'),
    path('homepage/stats/', homepage_api_views.get_platform_stats, name='platform_stats'),
    
    # ==================== MALL AUTHENTICATION (OTP-based) ====================
    path('mall/auth/request-otp/', mall_otp_auth_views.request_otp, name='mall_request_otp'),
    path('mall/auth/verify-otp/', mall_otp_auth_views.verify_otp, name='mall_verify_otp'),
    path('mall/auth/refresh-token/', mall_otp_auth_views.refresh_token, name='mall_refresh_token'),
    path('mall/auth/logout/', mall_otp_auth_views.logout, name='mall_logout'),
    path('mall/auth/profile/', mall_auth_views.get_profile, name='mall_profile'),
    path('mall/auth/update-profile/', mall_auth_views.update_profile, name='mall_update_profile'),
    
    # ==================== STORE OWNER MANAGEMENT ====================
    path('mall/store/register/', mall_auth_views.register_store_owner, name='register_store_owner'),
    path('mall/store/profile/', store_management_views.StoreProfileViewSet.as_view({'get': 'retrieve', 'put': 'update'}), name='store_profile'),
    path('mall/store/settings/', store_management_views.StoreSettingsViewSet.as_view({'get': 'retrieve', 'put': 'update'}), name='store_settings'),
    path('mall/store/themes/', store_management_views.get_available_themes, name='available_themes'),
    path('mall/store/themes/apply/', store_management_views.apply_theme, name='apply_theme'),
    path('mall/store/domain/setup/', store_management_views.setup_custom_domain, name='setup_domain'),
    path('mall/store/analytics/', store_management_views.get_store_analytics, name='store_analytics'),
    
    # ==================== MALL PRODUCT SYSTEM ====================
    # Product Classes (Root level)
    path('mall/product-classes/', mall_product_views.ProductClassViewSet.as_view({'get': 'list', 'post': 'create'}), name='product_classes'),
    path('mall/product-classes/<int:pk>/', mall_product_views.ProductClassViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='product_class_detail'),
    
    # Product Attributes (for inheritance)
    path('mall/product-attributes/', mall_product_views.ProductAttributeViewSet.as_view({'get': 'list', 'post': 'create'}), name='product_attributes'),
    path('mall/product-attributes/<int:pk>/', mall_product_views.ProductAttributeViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='product_attribute_detail'),
    path('mall/product-attributes/<int:pk>/values/', mall_product_views.get_attribute_values, name='attribute_values'),
    
    # Product Instances (only from leaf nodes)
    path('mall/product-instances/', mall_product_views.ProductInstanceViewSet.as_view({'get': 'list', 'post': 'create'}), name='product_instances'),
    path('mall/product-instances/<uuid:pk>/', mall_product_views.ProductInstanceViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='product_instance_detail'),
    path('mall/product-instances/<uuid:pk>/clone/', mall_product_views.clone_product_instance, name='clone_product_instance'),
    path('mall/product-instances/<uuid:pk>/stock-warning/', mall_product_views.check_stock_warning, name='stock_warning'),
    
    # Product Instance Variations (Colors, Sizes, etc.)
    path('mall/product-instances/<uuid:instance_id>/variations/', mall_product_views.ProductVariationViewSet.as_view({'get': 'list', 'post': 'create'}), name='product_variations'),
    path('mall/product-instances/<uuid:instance_id>/variations/<int:pk>/', mall_product_views.ProductVariationViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='product_variation_detail'),
    
    # ==================== SOCIAL MEDIA INTEGRATION ====================
    path('mall/social/extract/', mall_social_views.extract_social_content, name='extract_social_content'),
    path('mall/social/latest-posts/', mall_social_views.get_latest_social_posts, name='latest_social_posts'),
    path('mall/social/instagram/', enhanced_social_views.InstagramContentViewSet.as_view({'get': 'list'}), name='instagram_content'),
    path('mall/social/telegram/', enhanced_social_views.TelegramContentViewSet.as_view({'get': 'list'}), name='telegram_content'),
    path('mall/social/select-content/', enhanced_social_views.select_social_content, name='select_social_content'),
    path('mall/social/apply-to-product/', enhanced_social_views.apply_to_product, name='apply_social_to_product'),
    
    # ==================== STOREFRONT APIs (Customer-facing) ====================
    # Public store information
    path('storefront/<str:store_domain>/info/', storefront_views.get_store_info, name='public_store_info'),
    path('storefront/<str:store_domain>/products/', storefront_views.get_store_products, name='public_store_products'),
    path('storefront/<str:store_domain>/products/<uuid:product_id>/', storefront_views.get_product_detail, name='public_product_detail'),
    path('storefront/<str:store_domain>/categories/', storefront_views.get_store_categories, name='public_store_categories'),
    path('storefront/<str:store_domain>/search/', storefront_views.search_products, name='public_product_search'),
    
    # Product Lists (Recent, Most Viewed, Recommended)
    path('storefront/<str:store_domain>/products/recent/', storefront_views.get_recent_products, name='recent_products'),
    path('storefront/<str:store_domain>/products/most-viewed/', storefront_views.get_most_viewed_products, name='most_viewed_products'),
    path('storefront/<str:store_domain>/products/recommended/', recommendation_views.get_recommended_products, name='recommended_products'),
    path('storefront/<str:store_domain>/products/bestsellers/', storefront_views.get_bestselling_products, name='bestselling_products'),
    
    # ==================== CUSTOMER AUTHENTICATION ====================
    path('customer/auth/register/', customer_views.CustomerRegistrationView.as_view(), name='customer_register'),
    path('customer/auth/login/', customer_views.CustomerLoginView.as_view(), name='customer_login'),
    path('customer/auth/logout/', customer_views.CustomerLogoutView.as_view(), name='customer_logout'),
    path('customer/auth/profile/', customer_views.CustomerProfileView.as_view(), name='customer_profile'),
    path('customer/auth/change-password/', customer_views.CustomerChangePasswordView.as_view(), name='customer_change_password'),
    
    # ==================== SHOPPING CART & CHECKOUT ====================
    path('cart/', cart_views.CartViewSet.as_view({'get': 'retrieve'}), name='get_cart'),
    path('cart/add/', cart_views.CartViewSet.as_view({'post': 'add_item'}), name='add_to_cart'),
    path('cart/update/<int:item_id>/', cart_views.CartViewSet.as_view({'put': 'update_item'}), name='update_cart_item'),
    path('cart/remove/<int:item_id>/', cart_views.CartViewSet.as_view({'delete': 'remove_item'}), name='remove_from_cart'),
    path('cart/clear/', cart_views.CartViewSet.as_view({'delete': 'clear'}), name='clear_cart'),
    path('cart/checkout/', cart_views.checkout, name='checkout'),
    
    # ==================== ORDER MANAGEMENT ====================
    # Customer Orders
    path('customer/orders/', order_views.CustomerOrderViewSet.as_view({'get': 'list', 'post': 'create'}), name='customer_orders'),
    path('customer/orders/<uuid:pk>/', order_views.CustomerOrderViewSet.as_view({'get': 'retrieve'}), name='customer_order_detail'),
    path('customer/orders/<uuid:pk>/cancel/', order_views.CustomerOrderViewSet.as_view({'post': 'cancel'}), name='cancel_customer_order'),
    path('customer/orders/<uuid:pk>/track/', order_views.CustomerOrderViewSet.as_view({'get': 'track'}), name='track_customer_order'),
    
    # Store Owner Orders
    path('store/orders/', order_views.StoreOrderViewSet.as_view({'get': 'list'}), name='store_orders'),
    path('store/orders/<uuid:pk>/', order_views.StoreOrderViewSet.as_view({'get': 'retrieve', 'put': 'update'}), name='store_order_detail'),
    path('store/orders/<uuid:pk>/update-status/', order_views.StoreOrderViewSet.as_view({'post': 'update_status'}), name='update_order_status'),
    path('store/orders/<uuid:pk>/ship/', order_views.StoreOrderViewSet.as_view({'post': 'create_shipment'}), name='create_shipment'),
    path('store/orders/analytics/', order_views.get_order_analytics, name='order_analytics'),
    path('store/orders/export/', order_views.export_orders, name='export_orders'),
    
    # ==================== PAYMENT SYSTEM ====================
    path('payment/gateways/', payment_views.PaymentGatewayViewSet.as_view({'get': 'list'}), name='payment_gateways'),
    path('payment/gateways/<int:pk>/configure/', payment_views.PaymentGatewayViewSet.as_view({'post': 'configure'}), name='configure_payment_gateway'),
    path('payment/initiate/', payment_views.initiate_payment, name='initiate_payment'),
    path('payment/verify/', payment_views.verify_payment, name='verify_payment'),
    path('payment/callback/', payment_views.payment_callback, name='payment_callback'),
    path('payment/transactions/', payment_views.PaymentTransactionViewSet.as_view({'get': 'list'}), name='payment_transactions'),
    path('payment/transactions/<uuid:pk>/', payment_views.PaymentTransactionViewSet.as_view({'get': 'retrieve'}), name='payment_transaction_detail'),
    
    # ==================== LOGISTICS & SHIPPING ====================
    path('logistics/methods/', logistics_views.DeliveryMethodViewSet.as_view({'get': 'list', 'post': 'create'}), name='delivery_methods'),
    path('logistics/methods/<int:pk>/', logistics_views.DeliveryMethodViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='delivery_method_detail'),
    path('logistics/methods/<int:pk>/calculate-cost/', logistics_views.calculate_delivery_cost, name='calculate_delivery_cost'),
    path('logistics/shipments/', logistics_views.ShipmentViewSet.as_view({'get': 'list', 'post': 'create'}), name='shipments'),
    path('logistics/shipments/<int:pk>/', logistics_views.ShipmentViewSet.as_view({'get': 'retrieve', 'put': 'update'}), name='shipment_detail'),
    path('logistics/shipments/<int:pk>/track/', logistics_views.track_shipment, name='track_shipment'),
    path('logistics/shipments/track/<str:tracking_number>/', logistics_views.track_by_number, name='track_by_number'),
    
    # ==================== REVIEWS & RATINGS ====================
    path('products/<uuid:product_id>/reviews/', comment_views.ProductReviewViewSet.as_view({'get': 'list', 'post': 'create'}), name='product_reviews'),
    path('products/<uuid:product_id>/reviews/<int:pk>/', comment_views.ProductReviewViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='product_review_detail'),
    path('products/<uuid:product_id>/reviews/<int:pk>/helpful/', comment_views.mark_review_helpful, name='mark_review_helpful'),
    path('products/<uuid:product_id>/reviews/summary/', comment_views.get_review_summary, name='product_review_summary'),
    path('store/reviews/pending/', comment_views.get_pending_reviews, name='pending_reviews'),
    path('store/reviews/<int:review_id>/moderate/', comment_views.moderate_review, name='moderate_review'),
    
    # ==================== SEARCH & FILTERING ====================
    path('search/', search_views.ProductSearchView.as_view(), name='product_search'),
    path('search/suggestions/', search_views.get_search_suggestions, name='search_suggestions'),
    path('search/popular/', search_views.get_popular_searches, name='popular_searches'),
    path('search/advanced/', search_views.advanced_search, name='advanced_search'),
    path('search/filters/', search_views.get_available_filters, name='available_filters'),
    
    # ==================== ANALYTICS & REPORTS ====================
    # Platform Analytics (Admin only)
    path('admin/analytics/platform/', analytics_views.get_platform_analytics, name='platform_analytics'),
    path('admin/analytics/stores/', analytics_views.get_stores_analytics, name='stores_analytics'),
    
    # Store Analytics (Store Owner)
    path('store/analytics/dashboard/', analytics_views.get_store_dashboard, name='store_dashboard'),
    path('store/analytics/sales/', analytics_views.get_sales_analytics, name='sales_analytics'),
    path('store/analytics/products/', analytics_views.get_product_analytics, name='product_analytics'),
    path('store/analytics/customers/', analytics_views.get_customer_analytics, name='customer_analytics'),
    path('store/analytics/traffic/', analytics_views.get_traffic_analytics, name='traffic_analytics'),
    
    # ==================== RECOMMENDATIONS ====================
    path('recommendations/products/', recommendation_views.get_product_recommendations, name='product_recommendations'),
    path('recommendations/similar/<uuid:product_id>/', recommendation_views.get_similar_products, name='similar_products'),
    path('recommendations/frequently-bought/', recommendation_views.get_frequently_bought_together, name='frequently_bought'),
    path('recommendations/personalized/', recommendation_views.get_personalized_recommendations, name='personalized_recommendations'),
    
    # ==================== SMS CAMPAIGNS ====================
    path('sms/campaigns/', sms_campaign_views.SMSCampaignViewSet.as_view({'get': 'list', 'post': 'create'}), name='sms_campaigns'),
    path('sms/campaigns/<int:pk>/', sms_campaign_views.SMSCampaignViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='sms_campaign_detail'),
    path('sms/campaigns/<int:pk>/send/', sms_campaign_views.send_campaign, name='send_sms_campaign'),
    path('sms/campaigns/<int:pk>/analytics/', sms_campaign_views.get_campaign_analytics, name='sms_campaign_analytics'),
    path('sms/templates/', sms_campaign_views.SMSTemplateViewSet.as_view({'get': 'list', 'post': 'create'}), name='sms_templates'),
    path('sms/providers/', sms_campaign_views.get_sms_providers, name='sms_providers'),
    
    # ==================== LIVE CHAT ====================
    path('chat/conversations/', realtime_chat_views.ConversationViewSet.as_view({'get': 'list', 'post': 'create'}), name='chat_conversations'),
    path('chat/conversations/<uuid:pk>/', realtime_chat_views.ConversationViewSet.as_view({'get': 'retrieve'}), name='chat_conversation_detail'),
    path('chat/conversations/<uuid:conversation_id>/messages/', realtime_chat_views.MessageViewSet.as_view({'get': 'list', 'post': 'create'}), name='chat_messages'),
    path('chat/conversations/<uuid:conversation_id>/messages/<int:pk>/', realtime_chat_views.MessageViewSet.as_view({'get': 'retrieve'}), name='chat_message_detail'),
    path('chat/online-status/', realtime_chat_views.update_online_status, name='update_online_status'),
    
    # ==================== BULK OPERATIONS ====================
    # Product Import/Export
    path('bulk/products/import/', import_views.bulk_import_products, name='bulk_import_products'),
    path('bulk/products/export/', import_views.export_products, name='bulk_export_products'),
    path('bulk/products/validate/', import_views.validate_import_file, name='validate_import'),
    path('bulk/products/template/', import_views.download_import_template, name='import_template'),
    
    # Order Export
    path('bulk/orders/export/', order_views.export_orders, name='bulk_export_orders'),
    
    # ==================== CUSTOMER FEATURES ====================
    # Wishlist
    path('customer/wishlist/', customer_views.WishlistViewSet.as_view({'get': 'list'}), name='customer_wishlist'),
    path('customer/wishlist/add/', customer_views.WishlistViewSet.as_view({'post': 'add_item'}), name='add_to_wishlist'),
    path('customer/wishlist/remove/<uuid:product_id>/', customer_views.WishlistViewSet.as_view({'delete': 'remove_item'}), name='remove_from_wishlist'),
    
    # Addresses
    path('customer/addresses/', customer_views.CustomerAddressViewSet.as_view({'get': 'list', 'post': 'create'}), name='customer_addresses'),
    path('customer/addresses/<int:pk>/', customer_views.CustomerAddressViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='customer_address_detail'),
    
    # Order History
    path('customer/order-history/', customer_views.get_order_history, name='customer_order_history'),
    path('customer/order-history/<uuid:order_id>/', customer_views.get_order_detail, name='customer_order_detail'),
    
    # ==================== LEGACY SUPPORT ====================
    # Keep some legacy endpoints for backward compatibility
    path('api/auth/login/', authentication.login, name='legacy_login'),
    path('api/auth/register/', authentication.register, name='legacy_register'),
    path('api/products/', views.ProductListCreateView.as_view(), name='legacy_products'),
    path('api/categories/', views.CategoryListCreateView.as_view(), name='legacy_categories'),
]

# WebSocket URLs for real-time features
websocket_patterns = [
    path('ws/chat/<uuid:conversation_id>/', realtime_chat_views.ChatConsumer.as_asgi(), name='chat_websocket'),
    path('ws/notifications/<str:user_type>/<int:user_id>/', realtime_chat_views.NotificationConsumer.as_asgi(), name='notification_websocket'),
]

# Main URL patterns
urlpatterns = [
    # API v1
    path('api/v1/', include((api_v1_patterns, 'api_v1'), namespace='v1')),
    
    # Legacy API support
    path('api/', include((api_v1_patterns, 'api_legacy'), namespace='legacy')),
    
    # WebSocket URLs (if using Django Channels)
    # path('ws/', include(websocket_patterns)),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Health check endpoint
urlpatterns += [
    path('health/', views.health_check, name='health_check'),
    path('api/health/', views.api_health_check, name='api_health_check'),
]