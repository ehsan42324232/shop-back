from django.urls import path, include
from . import views, authentication, storefront_views, import_views, analytics_views
from . import search_views, order_views, comment_views, logistics_views
from .chat_urls import chat_urlpatterns

# API URLs
urlpatterns = [
    # ==================== Authentication ====================
    path('api/auth/register/', authentication.register, name='register'),
    path('api/auth/login/', authentication.login, name='login'),
    path('api/auth/logout/', authentication.logout, name='logout'),
    path('api/auth/profile/', authentication.profile, name='profile'),
    path('api/auth/update-profile/', authentication.update_profile, name='update_profile'),
    path('api/auth/change-password/', authentication.change_password, name='change_password'),
    path('api/auth/request-store/', authentication.request_store, name='request_store'),
    
    # ==================== Platform Admin APIs ====================
    # Store management (for platform admin)
    path('api/admin/stores/', views.AdminStoreListView.as_view(), name='admin_stores'),
    path('api/admin/stores/<uuid:pk>/', views.AdminStoreDetailView.as_view(), name='admin_store_detail'),
    path('api/admin/stores/<uuid:store_id>/approve/', views.approve_store, name='approve_store'),
    path('api/admin/stores/<uuid:store_id>/reject/', views.reject_store, name='reject_store'),
    
    # Platform analytics (admin only)
    path('api/admin/analytics/', analytics_views.get_platform_analytics, name='platform_analytics'),
    
    # ==================== Store Owner APIs ====================
    # Store management (for store owners)
    path('api/store/profile/', views.get_store_profile, name='store_profile'),
    path('api/store/update/', views.update_store_profile, name='update_store_profile'),
    path('api/store/settings/', views.get_store_settings, name='store_settings'),
    path('api/store/analytics/', analytics_views.get_store_analytics, name='store_analytics'),
    
    # Analytics and Reports
    path('api/analytics/sales/', analytics_views.get_sales_report, name='sales_report'),
    path('api/analytics/inventory/', analytics_views.get_inventory_report, name='inventory_report'),
    path('api/analytics/products/<uuid:product_id>/', analytics_views.get_product_analytics, name='product_analytics'),
    
    # Categories
    path('api/categories/', views.CategoryListCreateView.as_view(), name='categories'),
    path('api/categories/<int:pk>/', views.CategoryDetailView.as_view(), name='category_detail'),
    path('api/categories/<int:category_id>/products/', views.get_category_products, name='category_products'),
    
    # Products
    path('api/products/', views.ProductListCreateView.as_view(), name='products'),
    path('api/products/<uuid:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('api/products/<uuid:product_id>/images/', views.ProductImageListCreateView.as_view(), name='product_images'),
    path('api/products/<uuid:product_id>/attributes/', views.get_product_attributes, name='product_attributes'),
    path('api/products/<uuid:product_id>/update-stock/', views.update_product_stock, name='update_product_stock'),
    
    # Product Attributes
    path('api/attributes/', views.AttributeListCreateView.as_view(), name='attributes'),
    path('api/attributes/<int:pk>/', views.AttributeDetailView.as_view(), name='attribute_detail'),
    
    # Bulk Import/Export
    path('api/import/products/', import_views.bulk_import_products, name='bulk_import_products'),
    path('api/import/validate/', import_views.validate_import_file, name='validate_import_file'),
    path('api/import/logs/', import_views.get_import_logs, name='import_logs'),
    path('api/import/logs/<int:log_id>/', import_views.get_import_log_detail, name='import_log_detail'),
    path('api/import/logs/<int:log_id>/delete/', import_views.delete_import_log, name='delete_import_log'),
    path('api/import/statistics/', import_views.get_import_statistics, name='import_statistics'),
    path('api/import/template/', import_views.download_sample_template, name='download_sample_template'),
    path('api/export/products/', import_views.export_products, name='export_products'),
    
    # ==================== Advanced Search APIs ====================
    path('api/search/', search_views.ProductSearchView.as_view(), name='product_search'),
    path('api/search/suggestions/', search_views.search_suggestions, name='search_suggestions'),
    path('api/search/popular/', search_views.popular_searches, name='popular_searches'),
    path('api/search/log/', search_views.log_search, name='log_search'),
    
    # ==================== Order Management APIs ====================
    path('api/orders/', order_views.OrderViewSet.as_view({'get': 'list', 'post': 'create'}), name='orders'),
    path('api/orders/<int:pk>/', order_views.OrderViewSet.as_view({'get': 'retrieve', 'put': 'update'}), name='order_detail'),
    path('api/orders/<int:pk>/update-status/', order_views.OrderViewSet.as_view({'post': 'update_status'}), name='update_order_status'),
    path('api/orders/<int:pk>/cancel/', order_views.OrderViewSet.as_view({'post': 'cancel_order'}), name='cancel_order'),
    path('api/orders/<int:pk>/tracking/', order_views.OrderViewSet.as_view({'get': 'tracking_info'}), name='order_tracking'),
    path('api/orders/analytics/', order_views.order_analytics, name='order_analytics'),
    path('api/orders/bulk-update/', order_views.bulk_update_orders, name='bulk_update_orders'),
    path('api/orders/export/', order_views.export_orders, name='export_orders'),
    
    # ==================== Reviews and Comments APIs ====================
    path('api/products/<uuid:product_id>/reviews/', comment_views.ProductReviewViewSet.as_view({'get': 'list', 'post': 'create'}), name='product_reviews'),
    path('api/products/<uuid:product_id>/reviews/<int:pk>/', comment_views.ProductReviewViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='product_review_detail'),
    path('api/products/<uuid:product_id>/reviews/<int:pk>/helpful/', comment_views.ProductReviewViewSet.as_view({'post': 'mark_helpful'}), name='mark_review_helpful'),
    path('api/products/<uuid:product_id>/reviews/summary/', comment_views.ProductReviewViewSet.as_view({'get': 'summary'}), name='product_reviews_summary'),
    path('api/products/<uuid:product_id>/reviews/stats/', comment_views.product_reviews_stats, name='product_reviews_stats'),
    path('api/reviews/pending/', comment_views.pending_reviews, name='pending_reviews'),
    path('api/reviews/<int:review_id>/moderate/', comment_views.moderate_review, name='moderate_review'),
    path('api/reviews/bulk-moderate/', comment_views.bulk_moderate_reviews, name='bulk_moderate_reviews'),
    
    # ==================== Logistics and Shipping APIs ====================
    path('api/delivery-methods/', logistics_views.DeliveryMethodViewSet.as_view({'get': 'list', 'post': 'create'}), name='delivery_methods'),
    path('api/delivery-methods/<int:pk>/', logistics_views.DeliveryMethodViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='delivery_method_detail'),
    path('api/delivery-methods/<int:pk>/calculate-cost/', logistics_views.DeliveryMethodViewSet.as_view({'post': 'calculate_cost'}), name='calculate_delivery_cost'),
    path('api/delivery-methods/available/', logistics_views.available_delivery_methods, name='available_delivery_methods'),
    
    path('api/shipments/', logistics_views.ShipmentViewSet.as_view({'get': 'list'}), name='shipments'),
    path('api/shipments/<int:pk>/', logistics_views.ShipmentViewSet.as_view({'get': 'retrieve'}), name='shipment_detail'),
    path('api/shipments/<int:pk>/update-tracking/', logistics_views.ShipmentViewSet.as_view({'post': 'update_tracking'}), name='update_shipment_tracking'),
    path('api/shipments/<int:pk>/track/', logistics_views.ShipmentViewSet.as_view({'get': 'track'}), name='track_shipment_detail'),
    path('api/shipments/track/<str:tracking_number>/', logistics_views.track_shipment, name='track_shipment'),
    path('api/shipments/create/<int:order_id>/', logistics_views.create_shipment, name='create_shipment'),
    path('api/shipments/analytics/', logistics_views.logistics_analytics, name='logistics_analytics'),
    path('api/shipments/bulk-update/', logistics_views.bulk_update_shipments, name='bulk_update_shipments'),
    
    # ==================== Customer/Storefront APIs ====================
    # Public store info
    path('api/store/info/', views.get_store_info, name='store_info'),
    
    # Shopping Cart
    path('api/basket/', storefront_views.get_basket, name='get_basket'),
    path('api/basket/add/', storefront_views.add_to_basket, name='add_to_basket'),
    path('api/basket/<int:item_id>/update/', storefront_views.update_basket_item, name='update_basket_item'),
    path('api/basket/<int:item_id>/remove/', storefront_views.remove_from_basket, name='remove_from_basket'),
    path('api/basket/clear/', storefront_views.clear_basket, name='clear_basket'),
    
    # Orders (Customer view)
    path('api/customer/orders/', storefront_views.get_orders, name='customer_get_orders'),
    path('api/customer/orders/create/', storefront_views.create_order, name='customer_create_order'),
    path('api/customer/orders/<uuid:order_id>/', storefront_views.get_order_detail, name='customer_order_detail'),
    
    # Customer Addresses
    path('api/addresses/', storefront_views.get_addresses, name='get_addresses'),
    path('api/addresses/create/', storefront_views.create_address, name='create_address'),
    path('api/addresses/<int:address_id>/update/', storefront_views.update_address, name='update_address'),
    path('api/addresses/<int:address_id>/delete/', storefront_views.delete_address, name='delete_address'),
    
    # Wishlist
    path('api/wishlist/', storefront_views.get_wishlist, name='get_wishlist'),
    path('api/wishlist/add/', storefront_views.add_to_wishlist, name='add_to_wishlist'),
    path('api/wishlist/<int:item_id>/remove/', storefront_views.remove_from_wishlist, name='remove_from_wishlist'),
    
    # Delivery Info
    path('api/delivery/', storefront_views.get_delivery_info, name='delivery_info'),
    
    # ==================== Legacy URLs (if needed) ====================
    path('stores/', views.StoreListCreateView.as_view(), name='store-list'),
    path('stores/<uuid:pk>/', views.StoreDetailView.as_view(), name='store-detail'),
    path('stores/<uuid:store_id>/products/', views.get_store_products, name='store-products'),
]

# Add live chat URLs
urlpatterns += chat_urlpatterns

# Add any additional URL patterns for other views if they exist
try:
    from . import additional_views
    urlpatterns += [
        # Additional view patterns can be added here
    ]
except ImportError:
    pass

# Add social content URLs
try:
    from .social_content_urls import urlpatterns as social_urls
    urlpatterns += social_urls
except ImportError:
    pass
