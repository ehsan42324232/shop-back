from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from decimal import Decimal
import uuid


class TimestampedModel(models.Model):
    """Abstract base class with timestamp fields"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class Store(TimestampedModel):
    """Multi-tenant store model"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stores')
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True)
    domain = models.CharField(max_length=255, unique=True)
    logo = models.ImageField(upload_to='store_logos/', blank=True, null=True)
    
    # Store settings
    is_active = models.BooleanField(default=True)
    currency = models.CharField(max_length=3, default='USD')
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0000'))
    
    # Contact information
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    
    class Meta:
        db_table = 'shop_store'
        indexes = [
            models.Index(fields=['owner']),
            models.Index(fields=['is_active']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Category(TimestampedModel):
    """Product categories with hierarchical structure"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    image = models.ImageField(upload_to='category_images/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'shop_category'
        unique_together = ['store', 'slug']
        indexes = [
            models.Index(fields=['store', 'is_active']),
            models.Index(fields=['parent']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.store.name})"

    def get_full_path(self):
        """Get full category path (e.g., 'Electronics > Phones > Smartphones')"""
        path = [self.name]
        parent = self.parent
        while parent:
            path.append(parent.name)
            parent = parent.parent
        return ' > '.join(reversed(path))


class ProductAttribute(TimestampedModel):
    """Product attributes definition for each store"""
    ATTRIBUTE_TYPES = [
        ('text', 'Text'),
        ('number', 'Number'),
        ('boolean', 'Boolean'),
        ('choice', 'Choice'),
        ('color', 'Color'),
        ('date', 'Date'),
    ]
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='attributes')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, blank=True)
    attribute_type = models.CharField(max_length=20, choices=ATTRIBUTE_TYPES)
    is_required = models.BooleanField(default=False)
    is_filterable = models.BooleanField(default=True)
    is_searchable = models.BooleanField(default=False)
    choices = models.JSONField(default=list, blank=True)  # For choice type attributes
    unit = models.CharField(max_length=20, blank=True)  # For number type (e.g., 'kg', 'cm')
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'shop_product_attribute'
        unique_together = ['store', 'slug']
        indexes = [
            models.Index(fields=['store', 'is_filterable']),
            models.Index(fields=['attribute_type']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.store.name})"


class Product(TimestampedModel):
    """Enhanced product model with SEO and inventory management"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    
    # Basic information
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    short_description = models.CharField(max_length=500, blank=True)
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    compare_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Inventory
    sku = models.CharField(max_length=100, blank=True)
    barcode = models.CharField(max_length=100, blank=True)
    stock = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    low_stock_threshold = models.IntegerField(default=5)
    track_inventory = models.BooleanField(default=True)
    
    # Product attributes
    weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    dimensions = models.CharField(max_length=100, blank=True, help_text="L x W x H")
    
    # Status and visibility
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_digital = models.BooleanField(default=False)
    
    # SEO fields
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(max_length=320, blank=True)
    
    # Timestamps
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'shop_product'
        unique_together = ['store', 'slug']
        indexes = [
            models.Index(fields=['store', 'is_active']),
            models.Index(fields=['category']),
            models.Index(fields=['is_featured']),
            models.Index(fields=['sku']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def is_on_sale(self):
        return self.compare_price and self.price < self.compare_price

    @property
    def discount_percentage(self):
        if self.is_on_sale:
            return round(((self.compare_price - self.price) / self.compare_price) * 100, 2)
        return 0

    @property
    def is_low_stock(self):
        return self.track_inventory and self.stock <= self.low_stock_threshold

    @property
    def is_out_of_stock(self):
        return self.track_inventory and self.stock <= 0

    def __str__(self):
        return self.title


class ProductAttributeValue(TimestampedModel):
    """Product attribute values"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='attribute_values')
    attribute = models.ForeignKey(ProductAttribute, on_delete=models.CASCADE)
    value = models.TextField()
    
    class Meta:
        db_table = 'shop_product_attribute_value'
        unique_together = ['product', 'attribute']
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['attribute']),
        ]

    def __str__(self):
        return f"{self.product.title} - {self.attribute.name}: {self.value}"


class ProductImage(TimestampedModel):
    """Product images with ordering"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='product_images/')
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'shop_product_image'
        ordering = ['sort_order', 'created_at']


class Comment(TimestampedModel):
    """Product reviews and comments"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, blank=True)
    text = models.TextField()
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    helpful_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'shop_comment'
        indexes = [
            models.Index(fields=['product', 'is_approved']),
            models.Index(fields=['user']),
        ]


class Rating(TimestampedModel):
    """Product ratings (1-5 stars)"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        db_table = 'shop_rating'
        unique_together = ['product', 'user']


class Basket(TimestampedModel):
    """Shopping cart items"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='basket_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    
    # Store the price at time of adding to cart
    price_at_add = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'shop_basket'
        unique_together = ['user', 'product']

    def save(self, *args, **kwargs):
        if not self.price_at_add:
            self.price_at_add = self.product.price
        super().save(*args, **kwargs)

    @property
    def total_price(self):
        return self.price_at_add * self.quantity


class Order(TimestampedModel):
    """Customer orders"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=20, unique=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='orders')
    
    # Order details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    shipping_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    # Payment
    is_paid = models.BooleanField(default=False)
    payment_method = models.CharField(max_length=50, blank=True)
    payment_id = models.CharField(max_length=255, blank=True)
    
    # Shipping information
    shipping_address = models.JSONField(default=dict)
    billing_address = models.JSONField(default=dict)
    tracking_number = models.CharField(max_length=100, blank=True)
    
    # Timestamps
    confirmed_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'shop_order'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['store']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.order_number:
            # Generate order number: ORD-YYYYMMDD-XXXXX
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            count = Order.objects.filter(created_at__date=datetime.now().date()).count() + 1
            self.order_number = f"ORD-{date_str}-{count:05d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.order_number}"


class OrderItem(TimestampedModel):
    """Items in an order"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Store product details at time of order
    product_title = models.CharField(max_length=255)
    product_sku = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = 'shop_order_item'

    @property
    def total_price(self):
        return self.price_at_order * self.quantity

    def save(self, *args, **kwargs):
        if not self.product_title:
            self.product_title = self.product.title
        if not self.product_sku:
            self.product_sku = self.product.sku
        super().save(*args, **kwargs)


class BulkImportLog(TimestampedModel):
    """Track bulk import operations"""
    IMPORT_STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('partial', 'Partial Success'),
    ]
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='import_logs')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    status = models.CharField(max_length=20, choices=IMPORT_STATUS_CHOICES, default='processing')
    
    # Statistics
    total_rows = models.IntegerField(default=0)
    successful_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)
    categories_created = models.IntegerField(default=0)
    products_created = models.IntegerField(default=0)
    products_updated = models.IntegerField(default=0)
    
    # Error details
    error_details = models.JSONField(default=list)
    
    class Meta:
        db_table = 'shop_bulk_import_log'
        indexes = [
            models.Index(fields=['store', 'created_at']),
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"Import {self.filename} - {self.status}"
