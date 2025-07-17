from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Platform admin router
platform_router = DefaultRouter()
platform_router.register(r'stores', views.PlatformStoreViewSet, basename='platform-store')

# Store management router
store_router = DefaultRouter()
store_router.register(r'store-requests', views.StoreRequestViewSet, basename='store-request')
store_router.register(r'store-management', views.StoreManagementViewSet, basename='store-management')

# Store owner admin router
admin_router = DefaultRouter()
admin_router.register(r'categories', views.CategoryViewSet, basename='category')
admin_router.register(r'attributes', views.ProductAttributeViewSet, basename='attribute')
admin_router.register(r'products', views.ProductViewSet, basename='product')
admin_router.register(r'orders', views.OrderViewSet, basename='admin-order')
admin_router.register(r'delivery-zones', views.DeliveryZoneViewSet, basename='delivery-zone')
admin_router.register(r'payment-gateways', views.PaymentGatewayViewSet, basename='payment-gateway')
admin_router.register(r'import-logs', views.BulkImportLogViewSet, basename='import-log')

# Storefront router (for customers shopping on individual stores)
storefront_router = DefaultRouter()
storefront_router.register(r'products', views.ProductViewSet, basename='storefront-product')
storefront_router.register(r'categories', views.CategoryViewSet, basename='storefront-category')
storefront_router.register(r'basket', views.BasketViewSet, basename='basket')
storefront_router.register(r'orders', views.OrderViewSet, basename='order')
storefront_router.register(r'addresses', views.CustomerAddressViewSet, basename='address')
storefront_router.register(r'wishlist', views.WishlistViewSet, basename='wishlist')
storefront_router.register(r'comments', views.CommentViewSet, basename='comment')
storefront_router.register(r'ratings', views.RatingViewSet, basename='rating')

app_name = 'shop'

urlpatterns = [
    # Platform admin URLs (only for superusers)
    path('platform/', include(platform_router.urls)),
    
    # Store owner URLs (for requesting and managing stores)
    path('store/', include(store_router.urls)),
    
    # Store admin URLs (for store owners to manage their stores)
    path('admin/', include(admin_router.urls)),
    
    # Storefront URLs (for customers shopping)
    path('', include(storefront_router.urls)),
    
    # Additional custom endpoints
    path('search/', views.ProductSearchView.as_view(), name='product-search'),
    path('delivery-zones/calculate/', views.DeliveryCalculatorView.as_view(), name='delivery-calculate'),
    path('payment/process/', views.PaymentProcessView.as_view(), name='payment-process'),
    path('export/products/', views.ProductExportView.as_view(), name='product-export'),
    path('import/template/', views.ImportTemplateView.as_view(), name='import-template'),
]
