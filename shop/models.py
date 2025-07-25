# shop/models.py - Core Mall Platform Models
"""
Core models for the Mall Platform e-commerce system
This file consolidates all the essential models according to the product description
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
from django.utils.text import slugify


class MallUser(AbstractUser):
    """Extended user model for Mall platform"""
    USER_TYPES = [
        ('store_owner', 'Store Owner'),
        ('customer', 'Customer'),
        ('admin', 'Platform Admin'),
    ]
    
    phone = models.CharField(max_length=15, unique=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='customer')
    is_phone_verified = models.BooleanField(default=False)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    
    # Persian name support
    first_name_persian = models.CharField(max_length=30, blank=True)
    last_name_persian = models.CharField(max_length=30, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.username} ({self.phone})"


class Store(models.Model):
    """Store model for shop owners"""
    owner = models.OneToOneField(MallUser, on_delete=models.CASCADE, related_name='store')
    name = models.CharField(max_length=200)
    name_english = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField()
    
    # Domain settings  
    domain = models.CharField(max_length=100, unique=True)
    custom_domain = models.CharField(max_length=100, blank=True, null=True)
    
    # Store settings
    logo = models.ImageField(upload_to='store_logos/', blank=True, null=True)
    banner = models.ImageField(upload_to='store_banners/', blank=True, null=True)
    theme = models.CharField(max_length=50, default='default')
    
    # Contact information
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductClass(models.Model):
    """Hierarchical product classification system"""
    name = models.CharField(max_length=200)
    name_english = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(max_length=200, unique=True)
    
    # Hierarchy
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    level = models.PositiveIntegerField(default=0)
    
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='product_classes/', blank=True, null=True)
    
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Product Classes'
    
    def save(self, *args, **kwargs):
        if self.parent:
            self.level = self.parent.level + 1
        else:
            self.level = 0
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def is_leaf(self):
        """Check if this is a leaf node (can have product instances)"""
        return not self.children.exists()
    
    def __str__(self):
        return self.name


class ProductAttribute(models.Model):
    """Product attributes for customization"""
    ATTRIBUTE_TYPES = [
        ('text', 'Text'),
        ('number', 'Number'),
        ('color', 'Color'),
        ('choice', 'Single Choice'),
        ('multi_choice', 'Multiple Choice'),
        ('boolean', 'Yes/No'),
        ('image', 'Image'),
    ]
    
    name = models.CharField(max_length=100)
    name_english = models.CharField(max_length=100, blank=True)
    attribute_type = models.CharField(max_length=20, choices=ATTRIBUTE_TYPES)
    
    # Configuration
    is_required = models.BooleanField(default=False)
    is_categorizer = models.BooleanField(default=False)  # Level 1 children can categorize by this
    is_filterable = models.BooleanField(default=True)
    
    # For choice types
    choices = models.JSONField(blank=True, null=True)
    
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        return self.name


class ProductClassAttribute(models.Model):
    """Assign attributes to product classes"""
    product_class = models.ForeignKey(ProductClass, on_delete=models.CASCADE, related_name='class_attributes')
    attribute = models.ForeignKey(ProductAttribute, on_delete=models.CASCADE)
    
    # Override settings
    is_required = models.BooleanField(null=True, blank=True)
    is_categorizer = models.BooleanField(null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    class Meta:
        unique_together = ['product_class', 'attribute']
        ordering = ['sort_order']
    
    def __str__(self):
        return f"{self.product_class.name} - {self.attribute.name}"


class Product(models.Model):
    """Product instances (only from leaf nodes)"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products')
    product_class = models.ForeignKey(ProductClass, on_delete=models.CASCADE, related_name='products')
    
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    description = models.TextField()
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=0)
    compare_price = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=0, null=True, blank=True)
    
    # Inventory
    sku = models.CharField(max_length=100, unique=True, blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    track_inventory = models.BooleanField(default=True)
    
    # Media
    featured_image = models.ImageField(upload_to='products/', blank=True, null=True)
    
    # SEO
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    # Statistics
    view_count = models.PositiveIntegerField(default=0)
    sales_count = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    review_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['store', 'slug']
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.sku:
            self.sku = f"PROD-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    
    def is_in_stock(self):
        """Check if product is in stock"""
        if not self.track_inventory:
            return True
        return self.stock_quantity > 0
    
    def is_low_stock(self):
        """Check if only one item left (stock warning)"""
        return self.track_inventory and self.stock_quantity == 1
    
    def __str__(self):
        return f"{self.name} - {self.store.name}"


class ProductAttributeValue(models.Model):
    """Attribute values for products"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='attribute_values')
    attribute = models.ForeignKey(ProductAttribute, on_delete=models.CASCADE)
    value = models.TextField()  # JSON for complex values
    
    class Meta:
        unique_together = ['product', 'attribute']
    
    def __str__(self):
        return f"{self.product.name} - {self.attribute.name}: {self.value}"


class ProductMedia(models.Model):
    """Product images and videos"""
    MEDIA_TYPES = [
        ('image', 'Image'),
        ('video', 'Video'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='media')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES)
    file = models.FileField(upload_to='product_media/')
    title = models.CharField(max_length=200, blank=True)
    alt_text = models.CharField(max_length=200, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    # Social media source
    social_source = models.CharField(max_length=50, blank=True)  # 'instagram', 'telegram'
    social_url = models.URLField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['sort_order', '-created_at']
    
    def __str__(self):
        return f"{self.product.name} - {self.get_media_type_display()}"


class Cart(models.Model):
    """Shopping cart"""
    user = models.ForeignKey(MallUser, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True, null=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'store']
    
    def get_total(self):
        return sum(item.get_total() for item in self.items.all())
    
    def get_item_count(self):
        return sum(item.quantity for item in self.items.all())


class CartItem(models.Model):
    """Cart items"""
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['cart', 'product']
    
    def get_total(self):
        return self.product.price * self.quantity
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class Order(models.Model):
    """Orders"""
    ORDER_STATUS = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'), 
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=20, unique=True)
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='orders')
    customer = models.ForeignKey(MallUser, on_delete=models.CASCADE, related_name='orders')
    
    # Order details
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    
    # Amounts
    subtotal = models.DecimalField(max_digits=10, decimal_places=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    shipping_amount = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=0)
    
    # Customer info
    customer_name = models.CharField(max_length=200)
    customer_phone = models.CharField(max_length=15)
    customer_email = models.EmailField(blank=True)
    
    # Shipping address
    shipping_address = models.TextField()
    shipping_city = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=20)
    
    # Notes
    customer_notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            # Generate order number
            import random
            self.order_number = f"ORD-{random.randint(100000, 999999)}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Order {self.order_number} - {self.store.name}"


class OrderItem(models.Model):
    """Order items"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=0)
    
    # Store product details at time of order
    product_name = models.CharField(max_length=200)
    product_sku = models.CharField(max_length=100)
    
    def save(self, *args, **kwargs):
        self.total_price = self.unit_price * self.quantity
        self.product_name = self.product.name
        self.product_sku = self.product.sku
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.product_name} x {self.quantity}"


# Predefined attributes according to product description
def create_predefined_attributes():
    """Create predefined color and description attributes"""
    
    # Color attribute
    color_choices = [
        {'value': 'red', 'label': 'قرمز'},
        {'value': 'yellow', 'label': 'زرد'},
        {'value': 'blue', 'label': 'آبی'},
        {'value': 'green', 'label': 'سبز'},
        {'value': 'black', 'label': 'مشکی'},
        {'value': 'white', 'label': 'سفید'},
    ]
    
    color_attr, created = ProductAttribute.objects.get_or_create(
        name='رنگ',
        defaults={
            'name_english': 'Color',
            'attribute_type': 'color',
            'is_filterable': True,
            'choices': color_choices
        }
    )
    
    # Description attribute
    desc_attr, created = ProductAttribute.objects.get_or_create(
        name='توضیحات',
        defaults={
            'name_english': 'Description', 
            'attribute_type': 'text',
            'is_required': True
        }
    )
    
    # Sex attribute for clothing categorization
    sex_choices = [
        {'value': 'male', 'label': 'مردانه'},
        {'value': 'female', 'label': 'زنانه'},
    ]
    
    sex_attr, created = ProductAttribute.objects.get_or_create(
        name='جنسیت',
        defaults={
            'name_english': 'Sex',
            'attribute_type': 'choice',
            'is_categorizer': True,  # Can be used for subcategorization
            'choices': sex_choices
        }
    )
    
    # Size attribute
    size_choices = [
        {'value': 'xl', 'label': 'XL'},
        {'value': 'xxl', 'label': 'XXL'},
        {'value': 'l', 'label': 'L'},
        {'value': 'm', 'label': 'M'},
    ]
    
    size_attr, created = ProductAttribute.objects.get_or_create(
        name='سایز',
        defaults={
            'name_english': 'Size',
            'attribute_type': 'choice',
            'choices': size_choices
        }
    )
    
    return color_attr, desc_attr, sex_attr, size_attr
