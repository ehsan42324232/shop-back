"""
Refined models with additional functionality and optimizations
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
import uuid


class TimestampedModel(models.Model):
    """Base model with timestamp fields"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class Store(TimestampedModel):
    """Enhanced Store model with additional features"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    domain = models.CharField(max_length=255, unique=True)
    owner = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='owned_stores'
    )
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='store_logos/', blank=True, null=True)
    banner = models.ImageField(upload_to='store_banners/', blank=True, null=True)
    
    # Contact information
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    
    # Status and settings
    is_approved = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Store settings (JSON field for flexibility)
    settings = models.JSONField(default=dict, blank=True)
    
    # SEO fields
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    
    # Business information
    tax_number = models.CharField(max_length=50, blank=True)
    business_license = models.CharField(max_length=50, blank=True)
    
    class Meta:
        db_table = 'shop_store'
        ordering = ['name']
        indexes = [
            models.Index(fields=['domain']),
            models.Index(fields=['is_approved', 'is_active']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return f"https://{self.domain}/"
    
    @property
    def is_operational(self):
        """Check if store is ready for business"""
        return (
            self.is_approved and 
            self.is_active and 
            self.products.filter(is_active=True).exists()
        )


class Category(TimestampedModel):
    """Enhanced Category model with better hierarchy support"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(blank=True)
    description = models.TextField(blank=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='categories')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    
    # Display settings
    image = models.ImageField(upload_to='category_images/', blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, help_text='CSS icon class')
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    # SEO fields
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    
    class Meta:
        db_table = 'shop_category'
        unique_together = [['store', 'slug']]
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'categories'
        indexes = [
            models.Index(fields=['store', 'is_active']),
            models.Index(fields=['parent']),
        ]
    
    def __str__(self):
        return f"{self.store.name} - {self.name}"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('category_detail', kwargs={'slug': self.slug})
    
    @property
    def full_path(self):
        """Get full category path"""
        path = [self.name]
        parent = self.parent
        while parent:
            path.append(parent.name)
            parent = parent.parent
        return ' > '.join(reversed(path))


class Product(TimestampedModel):
    """Enhanced Product model with better features"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    slug = models.SlugField(blank=True)
    description = models.TextField(blank=True)
    short_description = models.TextField(max_length=500, blank=True)
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Inventory
    sku = models.CharField(max_length=100, unique=True, blank=True)
    barcode = models.CharField(max_length=100, blank=True)
    stock = models.PositiveIntegerField(default=0)
    track_inventory = models.BooleanField(default=True)
    
    # Physical properties
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    dimensions = models.CharField(max_length=100, blank=True, help_text='L x W x H')
    
    # Relationships
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    
    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_digital = models.BooleanField(default=False)
    
    # SEO fields
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    
    # Analytics
    view_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'shop_product'
        unique_together = [['store', 'slug']]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['store', 'is_active']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['is_featured', 'is_active']),
            models.Index(fields=['price']),
        ]
    
    def __str__(self):
        return f"{self.store.name} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if not self.sku:
            self.sku = f"{self.store.slug}-{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('product_detail', kwargs={'slug': self.slug})
    
    @property
    def is_in_stock(self):
        """Check if product is in stock"""
        return self.stock > 0 if self.track_inventory else True
    
    @property
    def discount_percentage(self):
        """Calculate discount percentage"""
        if self.compare_price and self.compare_price > self.price:
            return round(((self.compare_price - self.price) / self.compare_price) * 100)
        return 0
    
    @property
    def main_image(self):
        """Get main product image"""
        return self.images.first()


class ProductImage(TimestampedModel):
    """Enhanced Product Image model"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='product_images/')
    alt_text = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_main = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'shop_product_image'
        ordering = ['sort_order']
        indexes = [
            models.Index(fields=['product', 'sort_order']),
        ]
    
    def __str__(self):
        return f"{self.product.title} - Image {self.sort_order}"
    
    def save(self, *args, **kwargs):
        if self.is_main:
            # Ensure only one main image per product
            ProductImage.objects.filter(
                product=self.product,
                is_main=True
            ).update(is_main=False)
        super().save(*args, **kwargs)


class ProductVariant(TimestampedModel):
    """Product variants (size, color, etc.)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    
    # Variant options (JSON for flexibility)
    options = models.JSONField(default=dict)  # e.g., {"color": "red", "size": "L"}
    
    class Meta:
        db_table = 'shop_product_variant'
        unique_together = [['product', 'name']]
    
    def __str__(self):
        return f"{self.product.title} - {self.name}"


class ProductReview(TimestampedModel):
    """Product reviews and ratings"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=255, blank=True)
    comment = models.TextField(blank=True)
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'shop_product_review'
        unique_together = [['product', 'customer']]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.product.title} - {self.rating} stars"


class Wishlist(TimestampedModel):
    """Customer wishlist"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'shop_wishlist'
        unique_together = [['customer', 'product']]
    
    def __str__(self):
        return f"{self.customer.username} - {self.product.title}"


class Discount(TimestampedModel):
    """Discount codes and promotions"""
    DISCOUNT_TYPES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
        ('free_shipping', 'Free Shipping'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='discounts')
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Discount settings
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Usage limits
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    customer_usage_limit = models.PositiveIntegerField(default=1)
    
    # Validity
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    # Conditions
    minimum_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    maximum_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'shop_discount'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.store.name} - {self.code}"
    
    @property
    def is_valid(self):
        """Check if discount is currently valid"""
        from django.utils import timezone
        now = timezone.now()
        return (
            self.is_active and
            self.start_date <= now <= self.end_date and
            (self.usage_limit is None or self.usage_count < self.usage_limit)
        )


class NotificationTemplate(TimestampedModel):
    """Email/SMS notification templates"""
    TEMPLATE_TYPES = [
        ('order_confirmation', 'Order Confirmation'),
        ('order_shipped', 'Order Shipped'),
        ('order_delivered', 'Order Delivered'),
        ('password_reset', 'Password Reset'),
        ('welcome', 'Welcome'),
        ('low_stock', 'Low Stock Alert'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='notification_templates')
    template_type = models.CharField(max_length=50, choices=TEMPLATE_TYPES)
    name = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    content = models.TextField()
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'shop_notification_template'
        unique_together = [['store', 'template_type']]
    
    def __str__(self):
        return f"{self.store.name} - {self.name}"


class PaymentMethod(TimestampedModel):
    """Payment method configurations"""
    PAYMENT_TYPES = [
        ('bank_transfer', 'Bank Transfer'),
        ('digital_wallet', 'Digital Wallet'),
        ('cryptocurrency', 'Cryptocurrency'),
        ('cash_on_delivery', 'Cash on Delivery'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='payment_methods')
    name = models.CharField(max_length=255)
    payment_type = models.CharField(max_length=50, choices=PAYMENT_TYPES)
    description = models.TextField(blank=True)
    
    # Configuration (JSON for flexibility)
    configuration = models.JSONField(default=dict)
    
    # Display settings
    icon = models.ImageField(upload_to='payment_icons/', blank=True, null=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'shop_payment_method'
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        return f"{self.store.name} - {self.name}"


class ShippingMethod(TimestampedModel):
    """Shipping method configurations"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='shipping_methods')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Pricing
    base_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cost_per_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Delivery time
    min_delivery_days = models.PositiveIntegerField(default=1)
    max_delivery_days = models.PositiveIntegerField(default=7)
    
    # Conditions
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    maximum_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Display settings
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'shop_shipping_method'
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        return f"{self.store.name} - {self.name}"
    
    @property
    def delivery_time_display(self):
        """Human-readable delivery time"""
        if self.min_delivery_days == self.max_delivery_days:
            return f"{self.min_delivery_days} day{'s' if self.min_delivery_days > 1 else ''}"
        return f"{self.min_delivery_days}-{self.max_delivery_days} days"


class StoreAnalytics(TimestampedModel):
    """Store analytics data"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='analytics')
    date = models.DateField()
    
    # Visitor metrics
    visitors = models.PositiveIntegerField(default=0)
    page_views = models.PositiveIntegerField(default=0)
    unique_visitors = models.PositiveIntegerField(default=0)
    
    # Sales metrics
    orders = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Product metrics
    products_viewed = models.PositiveIntegerField(default=0)
    cart_additions = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'shop_store_analytics'
        unique_together = [['store', 'date']]
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.store.name} - {self.date}"
