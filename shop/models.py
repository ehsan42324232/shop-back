from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from decimal import Decimal
import uuid
import os


class TimestampedModel(models.Model):
    """Abstract base class with timestamp fields"""
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ به‌روزرسانی")
    
    class Meta:
        abstract = True


class Store(TimestampedModel):
    """Multi-tenant store model"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stores', verbose_name="مالک فروشگاه")
    name = models.CharField(max_length=255, verbose_name="نام فروشگاه")
    name_en = models.CharField(max_length=255, blank=True, verbose_name="نام انگلیسی فروشگاه")
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True, verbose_name="توضیحات")
    domain = models.CharField(max_length=255, unique=True, verbose_name="دامنه")
    logo = models.ImageField(upload_to='store_logos/', blank=True, null=True, verbose_name="لوگو")
    
    # Store settings
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    is_approved = models.BooleanField(default=False, verbose_name="تایید شده")
    currency = models.CharField(max_length=3, default='IRR', verbose_name="واحد پول")
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0000'), verbose_name="نرخ مالیات")
    
    # Contact information
    email = models.EmailField(blank=True, verbose_name="ایمیل")
    phone = models.CharField(max_length=20, blank=True, verbose_name="تلفن")
    address = models.TextField(blank=True, verbose_name="آدرس")
    
    # Platform admin fields
    admin_notes = models.TextField(blank=True, verbose_name="یادداشت‌های مدیر")
    requested_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ درخواست")
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ تایید")

    class Meta:
        db_table = 'shop_store'
        verbose_name = "فروشگاه"
        verbose_name_plural = "فروشگاه‌ها"
        indexes = [
            models.Index(fields=['owner']),
            models.Index(fields=['is_active', 'is_approved']),
            models.Index(fields=['domain']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name_en or self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Category(TimestampedModel):
    """Product categories with hierarchical structure"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='categories', verbose_name="فروشگاه")
    name = models.CharField(max_length=100, verbose_name="نام دسته‌بندی")
    slug = models.SlugField(max_length=100, blank=True)
    description = models.TextField(blank=True, verbose_name="توضیحات")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, 
                              related_name='children', verbose_name="دسته‌بندی والد")
    image = models.ImageField(upload_to='category_images/', blank=True, null=True, verbose_name="تصویر")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")

    class Meta:
        db_table = 'shop_category'
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"
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
        """Get full category path"""
        path = [self.name]
        parent = self.parent
        while parent:
            path.append(parent.name)
            parent = parent.parent
        return ' > '.join(reversed(path))


class ProductAttribute(TimestampedModel):
    """Product attributes definition for each store"""
    ATTRIBUTE_TYPES = [
        ('text', 'متن'),
        ('number', 'عدد'),
        ('boolean', 'بولی'),
        ('choice', 'انتخابی'),
        ('color', 'رنگ'),
        ('date', 'تاریخ'),
    ]
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='attributes', verbose_name="فروشگاه")
    name = models.CharField(max_length=100, verbose_name="نام ویژگی")
    slug = models.SlugField(max_length=100, blank=True)
    attribute_type = models.CharField(max_length=20, choices=ATTRIBUTE_TYPES, verbose_name="نوع ویژگی")
    is_required = models.BooleanField(default=False, verbose_name="اجباری")
    is_filterable = models.BooleanField(default=True, verbose_name="قابل فیلتر")
    is_searchable = models.BooleanField(default=False, verbose_name="قابل جستجو")
    choices = models.JSONField(default=list, blank=True, verbose_name="گزینه‌ها")
    unit = models.CharField(max_length=20, blank=True, verbose_name="واحد")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")

    class Meta:
        db_table = 'shop_product_attribute'
        verbose_name = "ویژگی محصول"
        verbose_name_plural = "ویژگی‌های محصول"
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
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products', verbose_name="فروشگاه")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, 
                                related_name='products', verbose_name="دسته‌بندی")
    
    # Basic information
    title = models.CharField(max_length=255, verbose_name="عنوان محصول")
    slug = models.SlugField(max_length=255, blank=True)
    description = models.TextField(blank=True, verbose_name="توضیحات")
    short_description = models.CharField(max_length=500, blank=True, verbose_name="توضیحات کوتاه")
    
    # Pricing
    price = models.DecimalField(max_digits=12, decimal_places=0, 
                               validators=[MinValueValidator(Decimal('0'))], verbose_name="قیمت")
    compare_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name="قیمت مقایسه")
    cost_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name="قیمت تمام‌شده")
    
    # Inventory
    sku = models.CharField(max_length=100, blank=True, verbose_name="کد محصول")
    barcode = models.CharField(max_length=100, blank=True, verbose_name="بارکد")
    stock = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name="موجودی")
    low_stock_threshold = models.IntegerField(default=5, verbose_name="حد کمبود موجودی")
    track_inventory = models.BooleanField(default=True, verbose_name="ردیابی موجودی")
    
    # Product attributes
    weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="وزن")
    dimensions = models.CharField(max_length=100, blank=True, help_text="L x W x H", verbose_name="ابعاد")
    
    # Status and visibility
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    is_featured = models.BooleanField(default=False, verbose_name="ویژه")
    is_digital = models.BooleanField(default=False, verbose_name="دیجیتال")
    
    # SEO fields
    meta_title = models.CharField(max_length=255, blank=True, verbose_name="عنوان متا")
    meta_description = models.TextField(max_length=320, blank=True, verbose_name="توضیحات متا")
    
    # Timestamps
    published_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ انتشار")

    class Meta:
        db_table = 'shop_product'
        verbose_name = "محصول"
        verbose_name_plural = "محصولات"
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
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='attribute_values', verbose_name="محصول")
    attribute = models.ForeignKey(ProductAttribute, on_delete=models.CASCADE, verbose_name="ویژگی")
    value = models.TextField(verbose_name="مقدار")
    
    class Meta:
        db_table = 'shop_product_attribute_value'
        verbose_name = "مقدار ویژگی محصول"
        verbose_name_plural = "مقادیر ویژگی محصول"
        unique_together = ['product', 'attribute']
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['attribute']),
        ]

    def __str__(self):
        return f"{self.product.title} - {self.attribute.name}: {self.value}"


class ProductImage(TimestampedModel):
    """Product images with ordering"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images', verbose_name="محصول")
    image = models.ImageField(upload_to='product_images/', verbose_name="تصویر")
    alt_text = models.CharField(max_length=255, blank=True, verbose_name="متن جایگزین")
    is_primary = models.BooleanField(default=False, verbose_name="تصویر اصلی")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")

    class Meta:
        db_table = 'shop_product_image'
        verbose_name = "تصویر محصول"
        verbose_name_plural = "تصاویر محصول"
        ordering = ['sort_order', 'created_at']


class Comment(TimestampedModel):
    """Product reviews and comments"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='comments', verbose_name="محصول")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="کاربر")
    title = models.CharField(max_length=255, blank=True, verbose_name="عنوان")
    text = models.TextField(verbose_name="متن نظر")
    is_verified_purchase = models.BooleanField(default=False, verbose_name="خرید تایید شده")
    is_approved = models.BooleanField(default=False, verbose_name="تایید شده")
    helpful_count = models.PositiveIntegerField(default=0, verbose_name="تعداد مفید")

    class Meta:
        db_table = 'shop_comment'
        verbose_name = "نظر"
        verbose_name_plural = "نظرات"
        indexes = [
            models.Index(fields=['product', 'is_approved']),
            models.Index(fields=['user']),
        ]


class Rating(TimestampedModel):
    """Product ratings (1-5 stars)"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='ratings', verbose_name="محصول")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="کاربر")
    score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="امتیاز")
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True, verbose_name="نظر")

    class Meta:
        db_table = 'shop_rating'
        verbose_name = "امتیاز"
        verbose_name_plural = "امتیازات"
        unique_together = ['product', 'user']


class BulkImportLog(TimestampedModel):
    """Track bulk import operations"""
    IMPORT_STATUS_CHOICES = [
        ('processing', 'در حال پردازش'),
        ('completed', 'تکمیل شده'),
        ('failed', 'ناموفق'),
        ('partial', 'موفقیت جزئی'),
    ]
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='import_logs', verbose_name="فروشگاه")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="کاربر")
    filename = models.CharField(max_length=255, verbose_name="نام فایل")
    file_path = models.CharField(max_length=500, verbose_name="مسیر فایل")
    status = models.CharField(max_length=20, choices=IMPORT_STATUS_CHOICES, default='processing', verbose_name="وضعیت")
    
    # Statistics
    total_rows = models.IntegerField(default=0, verbose_name="تعداد کل ردیف‌ها")
    successful_rows = models.IntegerField(default=0, verbose_name="ردیف‌های موفق")
    failed_rows = models.IntegerField(default=0, verbose_name="ردیف‌های ناموفق")
    categories_created = models.IntegerField(default=0, verbose_name="دسته‌بندی‌های ایجاد شده")
    products_created = models.IntegerField(default=0, verbose_name="محصولات ایجاد شده")
    products_updated = models.IntegerField(default=0, verbose_name="محصولات به‌روزرسانی شده")
    
    # Error details
    error_details = models.JSONField(default=list, verbose_name="جزئیات خطا")
    
    class Meta:
        db_table = 'shop_bulk_import_log'
        verbose_name = "لاگ ایمپورت گروهی"
        verbose_name_plural = "لاگ‌های ایمپورت گروهی"
        indexes = [
            models.Index(fields=['store', 'created_at']),
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"Import {self.filename} - {self.status}"


# Import storefront models to make them available
from .storefront_models import *
