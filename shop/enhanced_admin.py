# Enhanced Django Admin for Mall Platform
from django.contrib import admin
from django.utils.html import format_html
from .mall_models import (
    MallPlatformSettings, EnhancedProductCategory, ProductAttributeDefinition,
    EnhancedProduct, ProductInstance, SocialMediaContent, StoreRequest
)

@admin.register(MallPlatformSettings)
class MallPlatformSettingsAdmin(admin.ModelAdmin):
    list_display = ['platform_name', 'contact_email', 'is_active']
    fields = [
        ('platform_name', 'platform_name_en'),
        ('hero_title', 'hero_subtitle'),
        ('contact_email', 'contact_phone'),
        ('is_active',)
    ]

@admin.register(EnhancedProductCategory)
class EnhancedProductCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'store', 'level', 'is_leaf', 'is_active']
    list_filter = ['store', 'level', 'is_active']
    search_fields = ['name', 'store__name']

@admin.register(ProductInstance)
class ProductInstanceAdmin(admin.ModelAdmin):
    list_display = ['sku', 'product', 'price', 'stock_quantity', 'is_active']
    list_filter = ['product__store', 'is_active']
    search_fields = ['sku', 'product__name']

@admin.register(StoreRequest)
class StoreRequestAdmin(admin.ModelAdmin):
    list_display = ['store_name', 'full_name', 'email', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['store_name', 'full_name', 'email']