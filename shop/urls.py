from django.urls import path, include
from . import views, authentication, storefront_views, import_views

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
    
    # ==================== Store Owner APIs ====================
    # Store management (for store owners)
    path('api/store/profile/', views.get_store_profile, name='store_profile'),
    path('api/store/update/', views.update_store_profile, name='update_store_profile'),
    path('api/store/settings/', views.get_store_settings, name='store_settings'),
    path('api/store/analytics/', views.get_store_analytics, name='store_analytics'),
    
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
    
    # ==================== Customer/Storefront APIs ====================
    # Public store info
    path('api/store/info/', views.get_store_info, name='store_info'),
    path('api/search/', views.search_products, name='search_products'),
    
    # Shopping Cart
    path('api/basket/', storefront_views.get_basket, name='get_basket'),
    path('api/basket/add/', storefront_views.add_to_basket, name='add_to_basket'),
    path('api/basket/<int:item_id>/update/', storefront_views.update_basket_item, name='update_basket_item'),
    path('api/basket/<int:item_id>/remove/', storefront_views.remove_from_basket, name='remove_from_basket'),
    path('api/basket/clear/', storefront_views.clear_basket, name='clear_basket'),
    
    # Orders
    path('api/orders/', storefront_views.get_orders, name='get_orders'),
    path('api/orders/create/', storefront_views.create_order, name='create_order'),
    path('api/orders/<uuid:order_id>/', storefront_views.get_order_detail, name='order_detail'),
    
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
    
    # Comments and Ratings
    path('api/products/<uuid:product_id>/comments/', views.ProductCommentListCreateView.as_view(), name='product_comments'),
    path('api/products/<uuid:product_id>/ratings/', views.ProductRatingCreateView.as_view(), name='product_ratings'),
    
    # ==================== Legacy URLs (if needed) ====================
    path('stores/', views.StoreListCreateView.as_view(), name='store-list'),
    path('stores/<uuid:pk>/', views.StoreDetailView.as_view(), name='store-detail'),
    path('stores/<uuid:store_id>/products/', views.get_store_products, name='store-products'),
]

# Add any additional URL patterns for other views if they exist
try:
    from . import additional_views
    urlpatterns += [
        # Additional view patterns can be added here
    ]
except ImportError:
    pass
