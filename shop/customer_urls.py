from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .customer_views import (
    CustomerProfileViewSet, CustomerAddressViewSet, WalletTransactionViewSet,
    CustomerNotificationViewSet, CustomerWishlistViewSet, CustomerReviewViewSet
)

# Create router for customer APIs
router = DefaultRouter()
router.register(r'profile', CustomerProfileViewSet, basename='customer-profile')
router.register(r'addresses', CustomerAddressViewSet, basename='customer-address')
router.register(r'wallet-transactions', WalletTransactionViewSet, basename='wallet-transaction')
router.register(r'notifications', CustomerNotificationViewSet, basename='customer-notification')
router.register(r'wishlist', CustomerWishlistViewSet, basename='customer-wishlist')
router.register(r'reviews', CustomerReviewViewSet, basename='customer-review')

# Customer API URLs
urlpatterns = [
    path('api/customer/', include(router.urls)),
]

# Additional custom endpoints can be added here if needed
app_name = 'customer'
