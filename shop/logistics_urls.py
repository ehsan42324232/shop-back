# shop/logistics_urls.py
"""
Mall Platform - Logistics URL Configuration
"""
from django.urls import path
from . import logistics_views_v2

urlpatterns = [
    # Shipping calculation
    path('logistics/calculate/', logistics_views_v2.calculate_shipping, name='calculate_shipping'),
    path('logistics/validate-address/', logistics_views_v2.validate_address, name='validate_address'),
    
    # Shipment management
    path('logistics/orders/<int:order_id>/create-shipment/', logistics_views_v2.create_shipment, name='create_shipment'),
    path('logistics/track/<str:tracking_number>/', logistics_views_v2.track_shipment, name='track_shipment'),
    
    # Providers and cities
    path('logistics/providers/', logistics_views_v2.get_logistics_providers, name='get_logistics_providers'),
    path('logistics/cities/', logistics_views_v2.get_cities, name='get_cities'),
]
