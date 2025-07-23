# Public Storefront URLs
# Customer-facing store website URLs

from django.urls import path
from . import storefront_public_views, cart_views

urlpatterns = [
    # Public store pages
    path('api/public/stores/<str:store_domain>/', storefront_public_views.store_homepage, name='public_store_homepage'),
    path('api/public/stores/<str:store_domain>/products/', storefront_public_views.store_products, name='public_store_products'),
    
    # Shopping cart
    path('api/public/stores/<str:store_domain>/cart/', cart_views.get_cart, name='get_cart'),
    path('api/public/stores/<str:store_domain>/cart/add/', cart_views.add_to_cart, name='add_to_cart'),
    path('api/public/stores/<str:store_domain>/cart/items/<int:item_id>/', cart_views.update_cart_item, name='update_cart_item'),
    path('api/public/stores/<str:store_domain>/cart/items/<int:item_id>/remove/', cart_views.remove_from_cart, name='remove_from_cart'),
    path('api/public/stores/<str:store_domain>/cart/clear/', cart_views.clear_cart, name='clear_cart'),
]