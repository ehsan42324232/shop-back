from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets_with_attributes import (
    StoreViewSet, CategoryViewSet, ProductViewSet, ProductAttributeViewSet,
    BasketViewSet, OrderViewSet, CommentViewSet, RatingViewSet, 
    BulkImportLogViewSet, AuthViewSet
)
from .storefront_views import StorefrontViewSet, DomainConfigViewSet
from . import authentication

# Admin API Router
admin_router = DefaultRouter()
admin_router.register(r'stores', StoreViewSet)
admin_router.register(r'categories', CategoryViewSet)
admin_router.register(r'products', ProductViewSet)
admin_router.register(r'product-attributes', ProductAttributeViewSet)
admin_router.register(r'basket', BasketViewSet, basename='basket')
admin_router.register(r'orders', OrderViewSet, basename='order')
admin_router.register(r'comments', CommentViewSet)
admin_router.register(r'ratings', RatingViewSet, basename='rating')
admin_router.register(r'import-logs', BulkImportLogViewSet, basename='import-log')
admin_router.register(r'auth', AuthViewSet, basename='auth')

# Storefront API Router
storefront_router = DefaultRouter()
storefront_router.register(r'storefront', StorefrontViewSet, basename='storefront')
storefront_router.register(r'config', DomainConfigViewSet, basename='config')

urlpatterns = [
    # Admin API routes
    path('api/admin/', include(admin_router.urls)),
    
    # Storefront API routes (domain-specific)
    path('api/', include(storefront_router.urls)),
    
    # Public API routes
    path('api/', include(admin_router.urls)),
    
    # Authentication routes (backward compatibility)
    path('api/auth/login/', authentication.login, name='login'),
    path('api/auth/register/', authentication.register, name='register'),
    path('api/auth/logout/', authentication.logout, name='logout'),
    
    # Health check
    path('api/health/', lambda request: JsonResponse({'status': 'ok'})),
]

# Add domain-specific routes
from django.http import JsonResponse

def domain_health_check(request):
    """Health check that includes domain info"""
    store = getattr(request, 'store', None)
    return JsonResponse({
        'status': 'ok',
        'domain': request.get_host(),
        'store': {
            'id': str(store.id) if store else None,
            'name': store.name if store else None,
            'active': store.is_active if store else False
        } if store else None
    })

urlpatterns += [
    path('api/health/domain/', domain_health_check, name='domain_health'),
]
