from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets_with_attributes import (
    StoreViewSet, CategoryViewSet, ProductViewSet, ProductAttributeViewSet,
    BasketViewSet, OrderViewSet, CommentViewSet, RatingViewSet, 
    BulkImportLogViewSet, AuthViewSet
)
from . import authentication

router = DefaultRouter()
router.register(r'stores', StoreViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'products', ProductViewSet)
router.register(r'product-attributes', ProductAttributeViewSet)
router.register(r'basket', BasketViewSet, basename='basket')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'comments', CommentViewSet)
router.register(r'ratings', RatingViewSet, basename='rating')
router.register(r'import-logs', BulkImportLogViewSet, basename='import-log')
router.register(r'auth', AuthViewSet, basename='auth')

urlpatterns = [
    path('api/', include(router.urls)),
    # Keep backward compatibility
    path('api/auth/login/', authentication.login, name='login'),
    path('api/auth/register/', authentication.register, name='register'),
    path('api/auth/logout/', authentication.logout, name='logout'),
]
