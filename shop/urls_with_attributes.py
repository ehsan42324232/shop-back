# Extended URLs with Product Attributes Support
# Use this file when enabling advanced product attribute features

from django.urls import path, include
from . import views, authentication, storefront_views, import_views, analytics_views
from . import search_views, order_views, comment_views, logistics_views
from .chat_urls import chat_urlpatterns

# Import attribute-specific views (when implemented)
try:
    from . import attribute_views
except ImportError:
    attribute_views = None


# API URLs with Advanced Features
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
    path('api/admin/stores/', views.AdminStoreListView.as_view(), name='admin_stores'),
    path('api/admin/stores/<uuid:pk>/', views.AdminStoreDetailView.as_view(), name='admin_store_detail'),
    path('api/admin/stores/<uuid:store_id>/approve/', views.approve_store, name='approve_store'),
    path('api/admin/stores/<uuid:store_id>/reject/', views.reject_store, name='reject_store'),
    path('api/admin/analytics/', analytics_views.get_platform_analytics, name='platform_analytics'),
    
    # ==================== Store Owner APIs ====================
    path('api/store/profile/', views.get_store_profile, name='store_profile'),
    path('api/store/update/', views.update_store_profile, name='update_store_profile'),
    path('api/store/settings/', views.get_store_settings, name='store_settings'),
    path('api/store/analytics/', analytics_views.get_store_analytics, name='store_analytics'),
    
    # Analytics and Reports
    path('api/analytics/sales/', analytics_views.get_sales_report, name='sales_report'),
    path('api/analytics/inventory/', analytics_views.get_inventory_report, name='inventory_report'),
    path('api/analytics/products/<uuid:product_id>/', analytics_views.get_product_analytics, name='product_analytics'),
    
    # ==================== Product Attribute Management ====================
    # Product Attributes (Store Owner Only)
    path('api/product-attributes/', views.ProductAttributeListCreateView.as_view(), name='product_attributes'),
    path('api/product-attributes/<int:pk>/', views.ProductAttributeDetailView.as_view(), name='product_attribute_detail'),
    path('api/product-attributes/<int:pk>/values/', views.ProductAttributeValueListCreateView.as_view(), name='attribute_values'),
    
    # Attribute Values
    path('api/attribute-values/<int:pk>/', views.ProductAttributeValueDetailView.as_view(), name='attribute_value_detail'),
    
    # Product Variants
    path('api/products/<uuid:product_id>/variants/', views.ProductVariantListCreateView.as_view(), name='product_variants'),
    path('api/products/<uuid:product_id>/variants/generate/', views.generate_product_variants, name='generate_variants'),
    path('api/product-variants/<int:pk>/', views.ProductVariantDetailView.as_view(), name='product_variant_detail'),
    
    # Bulk Variant Operations
    path('api/products/<uuid:product_id>/variants/bulk-update/', views.bulk_update_variants, name='bulk_update_variants'),
    path('api/products/<uuid:product_id>/variants/bulk-create/', views.bulk_create_variants, name='bulk_create_variants'),
    
    # ==================== Enhanced Product Management ====================
    # Categories with Attributes
    path('api/categories/', views.CategoryListCreateView.as_view(), name='categories'),
    path('api/categories/<int:pk>/', views.CategoryDetailView.as_view(), name='category_detail'),
    path('api/categories/<int:category_id>/products/', views.get_category_products, name='category_products'),
    path('api/categories/<int:category_id>/attributes/', views.get_category_attributes, name='category_attributes'),
    
    # Products with Variants
    path('api/products/', views.ProductListCreateView.as_view(), name='products'),
    path('api/products/<uuid:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('api/products/<uuid:product_id>/images/', views.ProductImageListCreateView.as_view(), name='product_images'),
    path('api/products/<uuid:product_id>/attributes/', views.get_product_attributes, name='product_attributes'),
    path('api/products/<uuid:product_id>/update-stock/', views.update_product_stock, name='update_product_stock'),
    
    # Product Copy/Clone with Attributes
    path('api/products/<uuid:product_id>/clone/', views.clone_product, name='clone_product'),
    
    # ==================== Enhanced Import/Export ====================
    # Bulk Import with Variants
    path('api/import/products/', import_views.bulk_import_products, name='bulk_import_products'),
    path('api/import/products-with-variants/', import_views.bulk_import_products_with_variants, name='bulk_import_variants'),
    path('api/import/validate/', import_views.validate_import_file, name='validate_import_file'),
    path('api/import/logs/', import_views.get_import_logs, name='import_logs'),
    path('api/import/template/', import_views.download_sample_template, name='download_sample_template'),
    path('api/import/template/variants/', import_views.download_variants_template, name='download_variants_template'),
    
    # Export with Variants
    path('api/export/products/', import_views.export_products, name='export_products'),
    path('api/export/products-with-variants/', import_views.export_products_with_variants, name='export_variants'),
    path('api/export/attributes/', import_views.export_attributes, name='export_attributes'),
    
    # ==================== Advanced Search APIs ====================
    path('api/search/', search_views.ProductSearchView.as_view(), name='product_search'),
    path('api/search/suggestions/', search_views.search_suggestions, name='search_suggestions'),
    path('api/search/popular/', search_views.popular_searches, name='popular_searches'),
    path('api/search/log/', search_views.log_search, name='log_search'),
    
    # Attribute-based Search
    path('api/search/attributes/', search_views.attribute_search, name='attribute_search'),
    path('api/search/filters/', search_views.get_search_filters, name='search_filters'),
    
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
    path('api/store/info/', views.get_store_info, name='store_info'),
    
    # Shopping Cart with Variants
    path('api/basket/', storefront_views.get_basket, name='get_basket'),
    path('api/basket/add/', storefront_views.add_to_basket, name='add_to_basket'),
    path('api/basket/add-variant/', storefront_views.add_variant_to_basket, name='add_variant_to_basket'),
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
    
    # Wishlist with Variants
    path('api/wishlist/', storefront_views.get_wishlist, name='get_wishlist'),
    path('api/wishlist/add/', storefront_views.add_to_wishlist, name='add_to_wishlist'),
    path('api/wishlist/add-variant/', storefront_views.add_variant_to_wishlist, name='add_variant_to_wishlist'),
    path('api/wishlist/<int:item_id>/remove/', storefront_views.remove_from_wishlist, name='remove_from_wishlist'),
    
    # Product Comparison with Attributes
    path('api/compare/add/', storefront_views.add_to_comparison, name='add_to_comparison'),
    path('api/compare/remove/', storefront_views.remove_from_comparison, name='remove_from_comparison'),
    path('api/compare/list/', storefront_views.get_comparison_list, name='get_comparison_list'),
    path('api/compare/clear/', storefront_views.clear_comparison, name='clear_comparison'),
    
    # ==================== Advanced Store Features ====================
    # Store Customization
    path('api/store/banners/', views.StoreBannerListCreateView.as_view(), name='store_banners'),
    path('api/store/banners/<int:pk>/', views.StoreBannerDetailView.as_view(), name='store_banner_detail'),
    
    # Coupons and Discounts
    path('api/store/coupons/', views.CouponListCreateView.as_view(), name='store_coupons'),
    path('api/store/coupons/<int:pk>/', views.CouponDetailView.as_view(), name='store_coupon_detail'),
    path('api/store/coupons/validate/', views.validate_coupon, name='validate_coupon'),
    
    # Store Analytics with Attributes
    path('api/analytics/attributes/', analytics_views.get_attribute_analytics, name='attribute_analytics'),
    path('api/analytics/variants/', analytics_views.get_variant_analytics, name='variant_analytics'),
    
    # ==================== Public APIs ====================
    # Public product info with variants
    path('api/public/products/<uuid:product_id>/', views.get_public_product_detail, name='public_product_detail'),
    path('api/public/products/<uuid:product_id>/variants/', views.get_public_product_variants, name='public_product_variants'),
    
    # ==================== Legacy URLs ====================
    path('stores/', views.StoreListCreateView.as_view(), name='store-list'),
    path('stores/<uuid:pk>/', views.StoreDetailView.as_view(), name='store-detail'),
    path('stores/<uuid:store_id>/products/', views.get_store_products, name='store-products'),
]

# Add live chat URLs
urlpatterns += chat_urlpatterns

# Add social content URLs
try:
    from .social_content_urls import urlpatterns as social_urls
    urlpatterns += social_urls
except ImportError:
    pass

# Add attribute-specific URLs if available
if attribute_views:
    urlpatterns += [
        # Advanced attribute management
        path('api/attributes/templates/', attribute_views.get_attribute_templates, name='attribute_templates'),
        path('api/attributes/import/', attribute_views.import_attributes, name='import_attributes'),
        path('api/attributes/export/', attribute_views.export_attributes, name='export_attributes'),
        
        # Attribute analytics
        path('api/attributes/<int:attribute_id>/analytics/', attribute_views.get_attribute_analytics, name='attribute_analytics'),
        
        # Variant management
        path('api/variants/bulk-operations/', attribute_views.bulk_variant_operations, name='bulk_variant_operations'),
    ]