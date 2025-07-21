# Advanced Models for Enhanced Features
# This file extends the main models with additional functionality

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

from .models import Store, Product
from .storefront_models import Order, OrderItem


class ProductAttribute(models.Model):
    """
    Defines custom attributes for products (e.g., Color, Size, Material)
    """
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='product_attributes')
    name = models.CharField(max_length=100)  # e.g., "Color", "Size"
    
    ATTRIBUTE_TYPES = [
        ('text', 'Text'),
        ('number', 'Number'),
        ('color', 'Color'),
        ('image', 'Image'),
        ('boolean', 'Yes/No'),
        ('select', 'Select'),
        ('multiselect', 'Multi-Select'),
    ]
    attribute_type = models.CharField(max_length=20, choices=ATTRIBUTE_TYPES, default='text')
    
    is_required = models.BooleanField(default=False)
    is_variation = models.BooleanField(default=True)  # Affects pricing/inventory
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'name']
        unique_together = ['store', 'name']

    def __str__(self):
        return f'{self.name} ({self.store.name})'


class ProductAttributeValue(models.Model):
    """
    Defines possible values for an attribute (e.g., "Red", "Blue" for Color)
    """
    attribute = models.ForeignKey(ProductAttribute, on_delete=models.CASCADE, related_name='values')
    value = models.CharField(max_length=100)  # e.g., "Red", "Large"
    display_name = models.CharField(max_length=100, blank=True)  # For localization
    
    # Additional properties for different attribute types
    color_code = models.CharField(max_length=7, blank=True)  # For color attributes
    image = models.ImageField(upload_to='attributes/', blank=True)  # For image attributes
    extra_cost = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order', 'value']
        unique_together = ['attribute', 'value']

    def __str__(self):
        return f'{self.attribute.name}: {self.value}'

    def save(self, *args, **kwargs):
        if not self.display_name:
            self.display_name = self.value
        super().save(*args, **kwargs)


class ProductVariant(models.Model):
    """
    Represents a specific combination of attribute values for a product
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=100, unique=True)
    attribute_values = models.ManyToManyField(ProductAttributeValue, blank=True)
    
    # Variant-specific pricing and inventory
    price_adjustment = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    stock_quantity = models.PositiveIntegerField(default=0)
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Additional variant properties
    barcode = models.CharField(max_length=100, blank=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.product.name} - {self.sku}'

    @property
    def final_price(self):
        """Calculate final price including adjustments"""
        return self.product.price + self.price_adjustment

    def save(self, *args, **kwargs):
        if not self.sku:
            # Generate SKU automatically
            base_sku = self.product.sku or f"VAR-{self.product.id}"
            variant_count = ProductVariant.objects.filter(product=self.product).count()
            self.sku = f"{base_sku}-{variant_count + 1}"
        super().save(*args, **kwargs)


class ProductReview(models.Model):
    """
    Customer reviews and ratings for products
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey(User, on_delete=models.CASCADE)
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, null=True, blank=True)
    
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=200)
    comment = models.TextField()
    
    # Review status
    STATUS_CHOICES = [
        ('pending', 'در انتظار تأیید'),
        ('approved', 'تأیید شده'),
        ('rejected', 'رد شده'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Helpful votes
    helpful_count = models.PositiveIntegerField(default=0)
    unhelpful_count = models.PositiveIntegerField(default=0)
    
    # Review attributes
    pros = models.TextField(blank=True, help_text='نقاط مثبت')
    cons = models.TextField(blank=True, help_text='نقاط منفی')
    
    # Purchase verification
    verified_purchase = models.BooleanField(default=False)
    
    # Admin moderation
    admin_notes = models.TextField(blank=True)
    moderated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='moderated_reviews')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['product', 'customer']
        ordering = ['-created_at']

    def __str__(self):
        return f'نظر {self.customer.username} برای {self.product.name}'

    def save(self, *args, **kwargs):
        # Set verified purchase if order item exists
        if self.order_item and self.order_item.order.customer == self.customer:
            self.verified_purchase = True
        
        # Set approval timestamp
        if self.status == 'approved' and not self.approved_at:
            self.approved_at = timezone.now()
        
        super().save(*args, **kwargs)
        
        # Update product rating
        self.update_product_rating()

    def update_product_rating(self):
        """Update product average rating and review count"""
        from django.db.models import Avg
        
        approved_reviews = ProductReview.objects.filter(
            product=self.product,
            status='approved'
        )
        
        avg_rating = approved_reviews.aggregate(Avg('rating'))['rating__avg']
        review_count = approved_reviews.count()
        
        self.product.average_rating = avg_rating or 0
        self.product.review_count = review_count
        self.product.save(update_fields=['average_rating', 'review_count'])


class ReviewHelpful(models.Model):
    """
    Track helpful votes for reviews
    """
    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name='helpful_votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_helpful = models.BooleanField()  # True for helpful, False for unhelpful
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['review', 'user']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update review helpful counts
        self.review.helpful_count = ReviewHelpful.objects.filter(
            review=self.review, is_helpful=True
        ).count()
        self.review.unhelpful_count = ReviewHelpful.objects.filter(
            review=self.review, is_helpful=False
        ).count()
        self.review.save(update_fields=['helpful_count', 'unhelpful_count'])


class DeliveryMethod(models.Model):
    """
    Delivery methods configured by store owners
    """
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='delivery_methods')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Delivery types
    TYPE_CHOICES = [
        ('standard', 'ارسال عادی'),
        ('express', 'ارسال سریع'),
        ('overnight', 'ارسال فوری'),
        ('pickup', 'تحویل حضوری'),
        ('courier', 'پیک'),
    ]
    delivery_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    
    # Pricing
    base_cost = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    cost_per_kg = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    
    # Time estimates
    min_delivery_days = models.PositiveIntegerField(default=1)
    max_delivery_days = models.PositiveIntegerField(default=3)
    
    # Availability
    is_active = models.BooleanField(default=True)
    works_weekends = models.BooleanField(default=True)
    cutoff_time = models.TimeField(help_text='زمان آخرین سفارش برای ارسال در همان روز')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['delivery_type', 'name']

    def __str__(self):
        return f'{self.name} - {self.store.name}'

    def calculate_cost(self, order_total, weight=0, delivery_zone=None):
        """Calculate delivery cost for an order"""
        # Free shipping check
        if self.free_shipping_threshold and order_total >= self.free_shipping_threshold:
            return 0
        
        cost = self.base_cost
        
        # Add weight-based cost
        if weight > 0 and self.cost_per_kg > 0:
            cost += weight * self.cost_per_kg
        
        # Zone-based adjustments
        if delivery_zone and hasattr(delivery_zone, 'delivery_multiplier'):
            cost *= delivery_zone.delivery_multiplier
        
        return cost

    def get_estimated_delivery(self):
        """Get estimated delivery date range"""
        from datetime import timedelta
        now = timezone.now()
        
        # Add business days
        min_date = now + timedelta(days=self.min_delivery_days)
        max_date = now + timedelta(days=self.max_delivery_days)
        
        return {
            'min_date': min_date.date(),
            'max_date': max_date.date(),
            'description': f'{self.min_delivery_days}-{self.max_delivery_days} روز کاری'
        }


class Shipment(models.Model):
    """
    Shipment tracking for orders
    """
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='shipment')
    delivery_method = models.ForeignKey(DeliveryMethod, on_delete=models.CASCADE)
    
    # Shipment details
    tracking_number = models.CharField(max_length=100, unique=True)
    carrier = models.CharField(max_length=100, blank=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    dimensions = models.JSONField(default=dict, blank=True)  # {length, width, height}
    
    # Status tracking
    STATUS_CHOICES = [
        ('preparing', 'در حال آماده‌سازی'),
        ('picked_up', 'تحویل به پست'),
        ('in_transit', 'در حال ارسال'),
        ('out_for_delivery', 'در مسیر تحویل'),
        ('delivered', 'تحویل داده شده'),
        ('failed_delivery', 'عدم تحویل'),
        ('returned', 'مرجوع شده'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='preparing')
    
    # Dates
    shipped_at = models.DateTimeField(null=True, blank=True)
    estimated_delivery = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # Delivery details
    delivery_notes = models.TextField(blank=True)
    signature_required = models.BooleanField(default=False)
    delivered_to = models.CharField(max_length=200, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'ارسال {self.tracking_number} - سفارش {self.order.order_number}'

    def save(self, *args, **kwargs):
        if not self.tracking_number:
            self.tracking_number = self.generate_tracking_number()
        super().save(*args, **kwargs)

    def generate_tracking_number(self):
        """Generate unique tracking number"""
        import random
        import string
        
        prefix = self.order.store.name[:2].upper()
        random_part = ''.join(random.choices(string.digits, k=10))
        return f'{prefix}{random_part}'


class ShipmentTracking(models.Model):
    """
    Detailed shipment tracking events
    """
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='tracking_events')
    status = models.CharField(max_length=20, choices=Shipment.STATUS_CHOICES)
    location = models.CharField(max_length=200, blank=True)
    description = models.TextField()
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_at']

    def __str__(self):
        return f'{self.shipment.tracking_number} - {self.get_status_display()}'


class SearchLog(models.Model):
    """
    Log search queries for analytics
    """
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='search_logs')
    query = models.CharField(max_length=500)
    results_count = models.PositiveIntegerField(default=0)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'جستجو: {self.query} ({self.store.name})'


class ProductView(models.Model):
    """
    Track product page views
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='page_views')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    referrer = models.URLField(blank=True)
    session_key = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'بازدید {self.product.name}'


class StoreSettings(models.Model):
    """
    Extended store settings and configuration
    """
    store = models.OneToOneField(Store, on_delete=models.CASCADE, related_name='advanced_settings')
    
    # SEO Settings
    meta_keywords = models.TextField(blank=True)
    google_analytics_id = models.CharField(max_length=50, blank=True)
    google_tag_manager_id = models.CharField(max_length=50, blank=True)
    
    # Social Media
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    telegram_url = models.URLField(blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    
    # Business Settings
    business_hours = models.JSONField(default=dict, blank=True)  # Store operating hours
    holiday_dates = models.JSONField(default=list, blank=True)  # Closed dates
    
    # Notification Settings
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=True)
    
    # Feature Toggles
    enable_reviews = models.BooleanField(default=True)
    enable_wishlist = models.BooleanField(default=True)
    enable_coupons = models.BooleanField(default=True)
    enable_chat = models.BooleanField(default=True)
    
    # Payment Settings
    payment_gateways = models.JSONField(default=dict, blank=True)
    
    # Shipping Settings
    default_shipping_cost = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    
    # Advanced Settings
    custom_css = models.TextField(blank=True)
    custom_javascript = models.TextField(blank=True)
    header_scripts = models.TextField(blank=True)
    footer_scripts = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'تنظیمات {self.store.name}'


class StoreBanner(models.Model):
    """
    Store promotional banners
    """
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='banners')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='banners/')
    
    # Banner positioning
    POSITION_CHOICES = [
        ('header', 'سربرگ'),
        ('footer', 'پابرگ'),
        ('sidebar', 'نوار کناری'),
        ('popup', 'پاپ‌آپ'),
        ('carousel', 'اسلایدر'),
    ]
    position = models.CharField(max_length=20, choices=POSITION_CHOICES)
    
    # Link settings
    link_url = models.URLField(blank=True)
    link_text = models.CharField(max_length=100, blank=True)
    open_in_new_tab = models.BooleanField(default=False)
    
    # Display settings
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # Schedule
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position', 'display_order']

    def __str__(self):
        return f'{self.title} ({self.store.name})'

    @property
    def is_currently_active(self):
        """Check if banner should be displayed now"""
        if not self.is_active:
            return False
        
        now = timezone.now()
        
        if self.start_date and now < self.start_date:
            return False
        
        if self.end_date and now > self.end_date:
            return False
        
        return True


class Coupon(models.Model):
    """
    Store discount coupons
    """
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='coupons')
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Discount settings
    DISCOUNT_TYPES = [
        ('percentage', 'درصدی'),
        ('fixed', 'مبلغ ثابت'),
    ]
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Usage limits
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    user_usage_limit = models.PositiveIntegerField(default=1)
    
    # Conditions
    minimum_amount = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    maximum_discount = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    
    # Schedule
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    # Status
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['store', 'code']

    def __str__(self):
        return f'{self.code} - {self.store.name}'

    def is_valid(self, user=None, order_total=0):
        """Check if coupon is valid for use"""
        now = timezone.now()
        
        # Check if active
        if not self.is_active:
            return False, 'کوپن غیرفعال است'
        
        # Check date range
        if now < self.start_date:
            return False, 'کوپن هنوز فعال نشده'
        
        if now > self.end_date:
            return False, 'کوپن منقضی شده'
        
        # Check usage limit
        if self.usage_limit and self.usage_count >= self.usage_limit:
            return False, 'حد استفاده کوپن به پایان رسیده'
        
        # Check minimum amount
        if self.minimum_amount and order_total < self.minimum_amount:
            return False, f'حداقل مبلغ سفارش {self.minimum_amount:,} تومان است'
        
        # Check user usage (if user provided)
        if user:
            user_usage = CouponUsage.objects.filter(
                coupon=self,
                user=user
            ).count()
            
            if user_usage >= self.user_usage_limit:
                return False, 'شما قبلاً از این کوپن استفاده کرده‌اید'
        
        return True, 'کوپن معتبر است'

    def calculate_discount(self, order_total):
        """Calculate discount amount"""
        if self.discount_type == 'percentage':
            discount = (order_total * self.discount_value) / 100
        else:
            discount = self.discount_value
        
        # Apply maximum discount limit
        if self.maximum_discount:
            discount = min(discount, self.maximum_discount)
        
        return min(discount, order_total)


class CouponUsage(models.Model):
    """
    Track coupon usage
    """
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=0)
    used_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.coupon.code} - {self.user.username}'


# Add these fields to existing Product model via migration
# class Product:
#     # Additional fields for enhanced functionality
#     average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
#     review_count = models.PositiveIntegerField(default=0)
#     view_count = models.PositiveIntegerField(default=0)
#     sales_count = models.PositiveIntegerField(default=0)
#     
#     # SEO enhancements
#     canonical_url = models.URLField(blank=True)
#     structured_data = models.JSONField(default=dict, blank=True)
#     
#     # Social sharing
#     og_title = models.CharField(max_length=200, blank=True)
#     og_description = models.TextField(blank=True)
#     og_image = models.ImageField(upload_to='og_images/', blank=True)
