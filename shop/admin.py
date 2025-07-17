from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Store, Category, Product, ProductAttribute, ProductAttributeValue,
    ProductImage, Comment, Rating, BulkImportLog
)
from .storefront_models import (
    Basket, Order, OrderItem, DeliveryZone, PaymentGateway,
    CustomerAddress, Wishlist
)


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ['name', 'domain', 'owner', 'is_active', 'is_approved', 'created_at']
    list_filter = ['is_active', 'is_approved', 'currency', 'created_at']
    search_fields = ['name', 'domain', 'owner__username', 'owner__email']
    readonly_fields = ['id', 'slug', 'created_at', 'updated_at', 'requested_at']
    actions = ['approve_stores', 'reject_stores']
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('name', 'name_en', 'slug', 'domain', 'description', 'logo')
        }),
        ('مالک', {
            'fields': ('owner',)
        }),
        ('تنظیمات', {
            'fields': ('is_active', 'is_approved', 'currency', 'tax_rate')
        }),
        ('اطلاعات تماس', {
            'fields': ('email', 'phone', 'address')
        }),
        ('مدیریت پلتفرم', {
            'fields': ('admin_notes', 'approved_at')
        }),
        ('زمان‌ها', {
            'fields': ('created_at', 'updated_at', 'requested_at'),
            'classes': ('collapse',)
        })
    )
    
    def approve_stores(self, request, queryset):
        from datetime import datetime
        queryset.update(is_approved=True, approved_at=datetime.now())
        self.message_user(request, f'{queryset.count()} فروشگاه تایید شد.')
    approve_stores.short_description = "تایید فروشگاه‌های انتخاب شده"
    
    def reject_stores(self, request, queryset):
        queryset.update(is_approved=False, is_active=False)
        self.message_user(request, f'{queryset.count()} فروشگاه رد شد.')
    reject_stores.short_description = "رد فروشگاه‌های انتخاب شده"


class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'store', 'parent', 'is_active', 'sort_order']
    list_filter = ['store', 'is_active', 'parent']
    search_fields = ['name', 'store__name']
    readonly_fields = ['slug', 'created_at', 'updated_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(store__owner=request.user)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'alt_text', 'is_primary', 'sort_order']


class ProductAttributeValueInline(admin.TabularInline):
    model = ProductAttributeValue
    extra = 1
    fields = ['attribute', 'value']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['title', 'store', 'category', 'price', 'stock', 'is_active', 'created_at']
    list_filter = ['store', 'category', 'is_active', 'is_featured', 'created_at']
    search_fields = ['title', 'sku', 'store__name']
    readonly_fields = ['id', 'slug', 'created_at', 'updated_at']
    inlines = [ProductImageInline, ProductAttributeValueInline]
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('title', 'slug', 'category', 'description', 'short_description')
        }),
        ('قیمت‌گذاری', {
            'fields': ('price', 'compare_price', 'cost_price')
        }),
        ('موجودی', {
            'fields': ('sku', 'barcode', 'stock', 'low_stock_threshold', 'track_inventory')
        }),
        ('ویژگی‌های فیزیکی', {
            'fields': ('weight', 'dimensions')
        }),
        ('تنظیمات', {
            'fields': ('is_active', 'is_featured', 'is_digital')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('زمان‌ها', {
            'fields': ('published_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(store__owner=request.user)


@admin.register(ProductAttribute)
class ProductAttributeAdmin(admin.ModelAdmin):
    list_display = ['name', 'store', 'attribute_type', 'is_required', 'is_filterable']
    list_filter = ['store', 'attribute_type', 'is_required', 'is_filterable']
    search_fields = ['name', 'store__name']
    readonly_fields = ['slug', 'created_at', 'updated_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(store__owner=request.user)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product_title', 'price_at_order', 'total_price']
    fields = ['product', 'product_title', 'quantity', 'price_at_order', 'total_price']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'store', 'user', 'status', 'payment_status', 'total_amount', 'created_at']
    list_filter = ['store', 'status', 'payment_status', 'delivery_method', 'created_at']
    search_fields = ['order_number', 'user__username', 'customer_name', 'customer_phone']
    readonly_fields = ['id', 'order_number', 'final_amount', 'created_at', 'updated_at']
    inlines = [OrderItemInline]
    
    fieldsets = (
        ('اطلاعات سفارش', {
            'fields': ('order_number', 'user', 'store', 'status', 'payment_status')
        }),
        ('مبالغ', {
            'fields': ('total_amount', 'tax_amount', 'shipping_amount', 'discount_amount', 'final_amount')
        }),
        ('پرداخت', {
            'fields': ('payment_method', 'payment_id', 'payment_gateway')
        }),
        ('تحویل', {
            'fields': ('delivery_method', 'expected_delivery_date', 'tracking_number')
        }),
        ('آدرس‌ها', {
            'fields': ('shipping_address', 'billing_address'),
            'classes': ('collapse',)
        }),
        ('اطلاعات مشتری', {
            'fields': ('customer_name', 'customer_phone', 'customer_email')
        }),
        ('یادداشت‌ها', {
            'fields': ('customer_notes', 'admin_notes'),
            'classes': ('collapse',)
        }),
        ('زمان‌ها', {
            'fields': ('created_at', 'updated_at', 'confirmed_at', 'shipped_at', 'delivered_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(store__owner=request.user)


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'store', 'standard_price', 'express_price', 'is_active']
    list_filter = ['store', 'is_active', 'same_day_available']
    search_fields = ['name', 'store__name']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(store__owner=request.user)


@admin.register(PaymentGateway)
class PaymentGatewayAdmin(admin.ModelAdmin):
    list_display = ['store', 'gateway_type', 'is_active']
    list_filter = ['store', 'gateway_type', 'is_active']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(store__owner=request.user)


@admin.register(BulkImportLog)
class BulkImportLogAdmin(admin.ModelAdmin):
    list_display = ['filename', 'store', 'user', 'status', 'total_rows', 'successful_rows', 'failed_rows', 'created_at']
    list_filter = ['store', 'status', 'created_at']
    readonly_fields = [
        'filename', 'file_path', 'total_rows', 'successful_rows', 'failed_rows',
        'categories_created', 'products_created', 'products_updated', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('اطلاعات فایل', {
            'fields': ('filename', 'file_path', 'store', 'user')
        }),
        ('وضعیت', {
            'fields': ('status',)
        }),
        ('آمار', {
            'fields': ('total_rows', 'successful_rows', 'failed_rows', 'categories_created', 'products_created', 'products_updated')
        }),
        ('خطاها', {
            'fields': ('error_details',),
            'classes': ('collapse',)
        }),
        ('زمان‌ها', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(store__owner=request.user)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'title', 'is_approved', 'is_verified_purchase', 'created_at']
    list_filter = ['is_approved', 'is_verified_purchase', 'created_at']
    search_fields = ['title', 'text', 'user__username', 'product__title']
    actions = ['approve_comments', 'reject_comments']
    
    def approve_comments(self, request, queryset):
        queryset.update(is_approved=True)
        self.message_user(request, f'{queryset.count()} نظر تایید شد.')
    approve_comments.short_description = "تایید نظرات انتخاب شده"
    
    def reject_comments(self, request, queryset):
        queryset.update(is_approved=False)
        self.message_user(request, f'{queryset.count()} نظر رد شد.')
    reject_comments.short_description = "رد نظرات انتخاب شده"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(product__store__owner=request.user)


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'score', 'created_at']
    list_filter = ['score', 'created_at']
    search_fields = ['user__username', 'product__title']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(product__store__owner=request.user)


@admin.register(Basket)
class BasketAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'quantity', 'price_at_add', 'created_at']
    list_filter = ['created_at', 'product__store']
    search_fields = ['user__username', 'product__title']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(product__store__owner=request.user)


@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'recipient_name', 'city', 'is_default']
    list_filter = ['is_default', 'province', 'city']
    search_fields = ['user__username', 'recipient_name', 'title']


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'created_at']
    list_filter = ['created_at', 'product__store']
    search_fields = ['user__username', 'product__title']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(product__store__owner=request.user)


# Register the remaining models that don't have custom admin classes
admin.site.register(Category, CategoryAdmin)

# Customize admin site headers
admin.site.site_header = "پلتفرم فروشگاه‌های آنلاین"
admin.site.site_title = "مدیریت پلتفرم"
admin.site.index_title = "مدیریت پلتفرم فروشگاه‌های آنلاین"
