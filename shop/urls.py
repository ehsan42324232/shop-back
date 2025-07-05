from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StoreViewSet, CategoryViewSet, ProductViewSet, BasketViewSet, OrderViewSet
from . import authentication

router = DefaultRouter()
router.register(r'stores', StoreViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'products', ProductViewSet)
router.register(r'basket', BasketViewSet, basename='basket')
router.register(r'orders', OrderViewSet, basename='order')

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/auth/login/', authentication.login, name='login'),
    path('api/auth/register/', authentication.register, name='register'),
    path('api/auth/logout/', authentication.logout, name='logout'),
]
