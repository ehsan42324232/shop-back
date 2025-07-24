# Mall Platform Product Instance Models
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from .mall_user_models import Store, MallUser
from .mall_product_models import ProductClass, ProductAttribute, ProductMedia
import uuid
import json


class Product(models.Model):
    """Product instances - can only be created from leaf nodes"""
    STATUS_CHOICES = [
        ('draft', 'پیش‌نویس'),
        ('active', 'فعال'),
        ('inactive', 'غیرفعال'),
        ('out_of_stock', 'اتمام موجودی'),
        ('discontinued', 'متوقف شده'),
    ]
    
    # Basic information
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products')
    product_class = models.ForeignKey(ProductClass, on_delete=models.CASCADE, related_name='products')
    
    # Product identification
    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=200, db_index=True)
    sku = models.CharField(max_length=100, blank=True, db_index=True)  # Stock Keeping Unit
    
    # Pricing
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    compare_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    cost_per_item = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    
    # Inventory
    track_inventory = models.BooleanField(default=True)
    inventory_quantity = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=5)
    allow_backorders = models.BooleanField(default=False)
    
    # Status and visibility
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)
    is_featured = models.BooleanField(default=False)
    requires_shipping = models.BooleanField(default=True)
    
    # SEO and metadata
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    
    # Media
    media = models.ManyToManyField(ProductMedia, through='ProductMediaAssignment', related_name='products')
    
    # Statistics
    view_count = models.PositiveIntegerField(default=0)
    order_count = models.PositiveIntegerField(default=0)
    favorite_count = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'products'
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        ordering = ['-created_at']
        unique_together = ['store', 'slug']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['is_featured']),
            models.Index(fields=['price']),
            models.Index(fields=['created_at']),
            models.Index(fields=['store', 'status']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.store.name}"
    
    def save(self, *args, **kwargs):
        # Ensure product can only be created from leaf nodes
        if not self.product_class.is_leaf():
            raise ValueError("محصول تنها می‌تواند از دسته‌های پایانی ایجاد شود")
        
        # Generate unique slug
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.name, allow_unicode=True)
            slug = base_slug
            counter = 1
            
            while Product.objects.filter(store=self.store, slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            self.slug = slug
        
        # Set published_at when status changes to active
        if self.status == 'active' and not self.published_at:
            self.published_at = timezone.now()
        
        super().save(*args, **kwargs)
        
        # Update product class count
        self.product_class.update_product_count()
    
    def is_active(self):
        return self.status == 'active'
    
    def is_in_stock(self):
        if not self.track_inventory:
            return True
        return self.inventory_quantity > 0 or self.allow_backorders
    
    def is_low_stock(self):
        if not self.track_inventory:
            return False
        return self.inventory_quantity <= self.low_stock_threshold
    
    def get_discount_percentage(self):
        if self.compare_price and self.compare_price > self.price:
            return int(((self.compare_price - self.price) / self.compare_price) * 100)
        return 0
    
    def get_absolute_url(self):
        return f"{self.store.get_absolute_url()}/products/{self.slug}/"
    
    def get_admin_url(self):
        return f"/dashboard/stores/{self.store.id}/products/{self.id}/"
    
    def increment_view_count(self):
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    def get_main_image(self):
        """Get the main product image"""
        assignment = self.media_assignments.filter(is_primary=True, media__media_type='image').first()
        if assignment:
            return assignment.media
        
        # Fallback to first image
        assignment = self.media_assignments.filter(media__media_type='image').first()
        return assignment.media if assignment else None
    
    def get_all_images(self):
        """Get all product images"""
        return [assignment.media for assignment in 
                self.media_assignments.filter(media__media_type='image').order_by('sort_order')]
    
    def get_all_videos(self):
        """Get all product videos"""
        return [assignment.media for assignment in 
                self.media_assignments.filter(media__media_type='video').order_by('sort_order')]
    
    def can_be_purchased(self):
        """Check if product can be purchased"""
        return (
            self.is_active() and 
            self.is_in_stock() and 
            self.store.can_accept_orders()
        )
    
    def get_attribute_values(self):
        """Get all attribute values for this product"""
        return {
            attr_value.attribute.slug: attr_value.get_display_value()
            for attr_value in self.attribute_values.select_related('attribute')
        }


class ProductMediaAssignment(models.Model):
    """Association between products and media with ordering"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='media_assignments')
    media = models.ForeignKey(ProductMedia, on_delete=models.CASCADE, related_name='product_assignments')
    
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    alt_text = models.CharField(max_length=200, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'product_media_assignments'
        verbose_name = 'Product Media Assignment'
        verbose_name_plural = 'Product Media Assignments'
        unique_together = ['product', 'media']
        ordering = ['sort_order', 'created_at']
    
    def save(self, *args, **kwargs):
        # Ensure only one primary image per product
        if self.is_primary:
            ProductMediaAssignment.objects.filter(
                product=self.product,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.product.name} - {self.media.title or 'Media'}"


class ProductAttributeValue(models.Model):
    """Attribute values for specific products"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='attribute_values')
    attribute = models.ForeignKey(ProductAttribute, on_delete=models.CASCADE, related_name='product_values')
    
    # Value storage for different types
    value_text = models.TextField(blank=True)
    value_number = models.BigIntegerField(null=True, blank=True)
    value_decimal = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    value_boolean = models.BooleanField(null=True, blank=True)
    value_date = models.DateField(null=True, blank=True)
    value_datetime = models.DateTimeField(null=True, blank=True)
    value_json = models.JSONField(null=True, blank=True)  # For multi_choice and complex types
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'product_attribute_values'
        verbose_name = 'Product Attribute Value'
        verbose_name_plural = 'Product Attribute Values'
        unique_together = ['product', 'attribute']
        ordering = ['attribute__sort_order']
    
    def __str__(self):
        return f"{self.product.name} - {self.attribute.name}: {self.get_display_value()}"
    
    def set_value(self, value):
        """Set value based on attribute type"""
        attribute_type = self.attribute.attribute_type
        
        # Clear all value fields first
        self.value_text = ''
        self.value_number = None
        self.value_decimal = None
        self.value_boolean = None
        self.value_date = None
        self.value_datetime = None
        self.value_json = None
        
        if not value:
            return
        
        # Set appropriate field based on type
        if attribute_type == 'text':
            self.value_text = str(value)
        elif attribute_type == 'number':
            self.value_number = int(value)
        elif attribute_type == 'decimal':
            self.value_decimal = float(value)
        elif attribute_type == 'boolean':
            self.value_boolean = bool(value)
        elif attribute_type == 'date':
            self.value_date = value
        elif attribute_type == 'datetime':
            self.value_datetime = value
        elif attribute_type in ['choice', 'color', 'url', 'email', 'phone']:
            self.value_text = str(value)
        elif attribute_type == 'multi_choice':
            self.value_json = value if isinstance(value, list) else [value]
        elif attribute_type in ['image', 'file']:
            self.value_text = str(value)  # Store file path/URL
        else:
            self.value_text = str(value)
    
    def get_value(self):
        """Get raw value based on attribute type"""
        attribute_type = self.attribute.attribute_type
        
        if attribute_type == 'text':
            return self.value_text
        elif attribute_type == 'number':
            return self.value_number
        elif attribute_type == 'decimal':
            return self.value_decimal
        elif attribute_type == 'boolean':
            return self.value_boolean
        elif attribute_type == 'date':
            return self.value_date
        elif attribute_type == 'datetime':
            return self.value_datetime
        elif attribute_type == 'multi_choice':
            return self.value_json
        elif attribute_type in ['choice', 'color', 'url', 'email', 'phone', 'image', 'file']:
            return self.value_text
        else:
            return self.value_text
    
    def get_display_value(self):
        """Get human-readable display value"""
        raw_value = self.get_value()
        
        if not raw_value:
            return ''
        
        attribute_type = self.attribute.attribute_type
        
        if attribute_type == 'boolean':
            return 'بله' if raw_value else 'خیر'
        elif attribute_type in ['choice', 'color']:
            # Look up display label from choices
            choices = self.attribute.get_choices()
            for choice in choices:
                if choice['value'] == raw_value:
                    return choice['label']
            return str(raw_value)
        elif attribute_type == 'multi_choice':
            if isinstance(raw_value, list):
                choices = self.attribute.get_choices()
                labels = []
                for value in raw_value:
                    for choice in choices:
                        if choice['value'] == value:
                            labels.append(choice['label'])
                            break
                    else:
                        labels.append(str(value))
                return ', '.join(labels)
            return str(raw_value)
        elif attribute_type == 'decimal':
            unit = self.attribute.unit
            if unit:
                return f"{raw_value} {unit}"
            return str(raw_value)
        elif attribute_type == 'number':
            unit = self.attribute.unit
            if unit:
                return f"{raw_value} {unit}"
            return str(raw_value)
        else:
            return str(raw_value)
    
    def validate(self):
        """Validate the attribute value"""
        return self.attribute.validate_value(self.get_value())


class ProductVariant(models.Model):
    """Product variants for products with multiple options (e.g., different colors/sizes)"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    
    # Variant identification
    name = models.CharField(max_length=200)  # e.g., "قرمز - XL"
    sku = models.CharField(max_length=100, blank=True, unique=True)
    
    # Pricing (can override product pricing)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    compare_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    
    # Inventory specific to this variant
    inventory_quantity = models.IntegerField(default=0)
    
    # Variant-specific media
    image = models.ForeignKey(ProductMedia, on_delete=models.SET_NULL, null=True, blank=True, related_name='variant_images')
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Variant attributes (e.g., color=red, size=XL)
    attributes_json = models.JSONField(default=dict)  # {attribute_slug: value}
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'product_variants'
        verbose_name = 'Product Variant'
        verbose_name_plural = 'Product Variants'
        ordering = ['name']
        unique_together = ['product', 'name']
    
    def __str__(self):
        return f"{self.product.name} - {self.name}"
    
    def get_effective_price(self):
        """Get effective price (variant price or product price)"""
        return self.price if self.price is not None else self.product.price
    
    def get_effective_compare_price(self):
        """Get effective compare price"""
        return self.compare_price if self.compare_price is not None else self.product.compare_price
    
    def is_in_stock(self):
        """Check if variant is in stock"""
        if not self.product.track_inventory:
            return True
        return self.inventory_quantity > 0 or self.product.allow_backorders
    
    def get_discount_percentage(self):
        """Get discount percentage for this variant"""
        effective_price = self.get_effective_price()
        effective_compare_price = self.get_effective_compare_price()
        
        if effective_compare_price and effective_compare_price > effective_price:
            return int(((effective_compare_price - effective_price) / effective_compare_price) * 100)
        return 0
    
    def get_attribute_display(self):
        """Get human-readable attribute display"""
        if not self.attributes_json:
            return self.name
        
        display_parts = []
        for attr_slug, value in self.attributes_json.items():
            try:
                attribute = ProductAttribute.objects.get(slug=attr_slug)
                if attribute.attribute_type in ['choice', 'color']:
                    choices = attribute.get_choices()
                    for choice in choices:
                        if choice['value'] == value:
                            display_parts.append(choice['label'])
                            break
                    else:
                        display_parts.append(str(value))
                else:
                    display_parts.append(str(value))
            except ProductAttribute.DoesNotExist:
                display_parts.append(str(value))
        
        return ' - '.join(display_parts)


class ProductReview(models.Model):
    """Product reviews and ratings"""
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey(MallUser, on_delete=models.CASCADE, related_name='product_reviews')
    
    # Review content
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    rating = models.IntegerField(choices=RATING_CHOICES, validators=[MinValueValidator(1), MaxValueValidator(5)])
    
    # Review metadata
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    helpful_count = models.PositiveIntegerField(default=0)
    
    # Response from store owner
    store_response = models.TextField(blank=True)
    store_response_date = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'product_reviews'
        verbose_name = 'Product Review'
        verbose_name_plural = 'Product Reviews'
        ordering = ['-created_at']
        unique_together = ['product', 'customer']  # One review per customer per product
        indexes = [
            models.Index(fields=['rating']),
            models.Index(fields=['is_approved']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.product.name} - {self.customer.get_display_name()} ({self.rating}⭐)"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update product rating statistics
        self.product.update_rating_stats()
    
    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        # Update product rating statistics after deletion
        self.product.update_rating_stats()


class ProductWishlist(models.Model):
    """Customer wishlist/favorites"""
    customer = models.ForeignKey(MallUser, on_delete=models.CASCADE, related_name='wishlist_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlist_items')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'product_wishlists'
        verbose_name = 'Product Wishlist'
        verbose_name_plural = 'Product Wishlists'
        unique_together = ['customer', 'product']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.customer.get_display_name()} - {self.product.name}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update product favorite count
        self.product.favorite_count = self.product.wishlist_items.count()
        self.product.save(update_fields=['favorite_count'])
    
    def delete(self, *args, **kwargs):
        product = self.product
        super().delete(*args, **kwargs)
        # Update product favorite count
        product.favorite_count = product.wishlist_items.count()
        product.save(update_fields=['favorite_count'])


# Add method to Product model for rating statistics
def update_rating_stats(self):
    """Update product rating statistics"""
    reviews = self.reviews.filter(is_approved=True)
    
    if reviews.exists():
        from django.db.models import Avg, Count
        stats = reviews.aggregate(
            avg_rating=Avg('rating'),
            review_count=Count('id')
        )
        
        # You could add these fields to Product model if needed
        # self.avg_rating = stats['avg_rating']
        # self.review_count = stats['review_count']
        # self.save(update_fields=['avg_rating', 'review_count'])

# Monkey patch the method to Product model
Product.update_rating_stats = update_rating_stats


class ProductImportTemplate(models.Model):
    """Template for bulk product imports"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='import_templates')
    name = models.CharField(max_length=200)
    
    # Template configuration
    product_class = models.ForeignKey(ProductClass, on_delete=models.CASCADE)
    field_mappings = models.JSONField()  # Map CSV columns to product fields
    default_values = models.JSONField(default=dict)  # Default values for missing fields
    
    # Import settings
    skip_first_row = models.BooleanField(default=True)  # Skip header row
    delimiter = models.CharField(max_length=5, default=',')
    encoding = models.CharField(max_length=20, default='utf-8')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'product_import_templates'
        verbose_name = 'Product Import Template'
        verbose_name_plural = 'Product Import Templates'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.store.name} - {self.name}"
