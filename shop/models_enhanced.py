from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.utils.text import slugify
from django.utils import timezone
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
    """Multi-tenant store model with domain support"""
    
    STATUS_CHOICES = [
        ('pending', 'در انتظار بررسی'),
        ('approved', 'تایید شده'),
        ('suspended', 'تعلیق شده'),
        ('rejected', 'رد شده'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stores', verbose_name="مالک فروشگاه")
    
    # Store Information
    name = models.CharField(max_length=255, verbose_name="نام فروشگاه")
    name_en = models.CharField(max_length=255, blank=True, verbose_name="نام انگلیسی فروشگاه")
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True, verbose_name="توضیحات")
    logo = models.ImageField(upload_to='store_logos/', blank=True, null=True, verbose_name="لوگو")
    
    # Domain Configuration
    domain = models.CharField(
        max_length=255, 
        unique=True, 
        verbose_name="دامنه",
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.([a-zA-Z]{2,})$',
                message="لطفا یک دامنه معتبر وارد کنید"
            )
        ],
        help_text="مثال: myshop.com"
    )
    is_ssl_enabled = models.BooleanField(default=True, verbose_name="SSL فعال")
    
    # Store Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="وضعیت")
    is_active = models.BooleanField(default=False, verbose_name="فعال")
    
    # Business Information
    business_license = models.CharField(max_length=100, blank=True, verbose_name="شماره جواز کسب")
    tax_id = models.CharField(max_length=50, blank=True, verbose_name="شناسه مالیاتی")
    
    # Store Settings
    currency = models.CharField(max_length=3, default='IRR', verbose_name="واحد پول")
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.0900'), verbose_name="نرخ مالیات")
    
    # Contact Information
    email = models.EmailField(verbose_name="ایمیل")
    phone = models.CharField(max_length=20, verbose_name="تلفن")
    address = models.TextField(verbose_name="آدرس")
    
    # Store Theme & Customization
    primary_color = models.CharField(max_length=7, default='#3B82F6', verbose_name="رنگ اصلی")
    secondary_color = models.CharField(max_length=7, default='#1E40AF', verbose_name="رنگ ثانویه")
    custom_css = models.TextField(blank=True, verbose_name="CSS سفارشی")
    
    # Platform Admin Fields
    admin_notes = models.TextField(blank=True, verbose_name="یادداشت‌های مدیر")
    requested_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ درخواست")
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ تایید")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='approved_stores', verbose_name="تایید شده توسط")

    class Meta:
        db_table = 'shop_store_enhanced'
        verbose_name = "فروشگاه"
        verbose_name_plural = "فروشگاه‌ها"
        indexes = [
            models.Index(fields=['owner']),
            models.Index(fields=['status', 'is_active']),
            models.Index(fields=['domain']),
            models.Index(fields=['created_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name_en or self.name)
        
        # Auto-approve if status changed to approved
        if self.status == 'approved' and not self.approved_at:
            self.approved_at = timezone.now()
            self.is_active = True
            
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
    
    @property
    def full_domain(self):
        protocol = 'https' if self.is_ssl_enabled else 'http'
        return f"{protocol}://{self.domain}"


class StoreRequest(TimestampedModel):
    """Store creation requests"""
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="متقاضی")
    
    # Requested Store Info
    store_name = models.CharField(max_length=255, verbose_name="نام فروشگاه")
    desired_domain = models.CharField(max_length=255, verbose_name="دامنه مورد نظر")
    business_type = models.CharField(max_length=100, verbose_name="نوع کسب و کار")
    description = models.TextField(verbose_name="توضیحات")
    
    # Business Documents
    business_license_file = models.FileField(upload_to='store_requests/documents/', 
                                           blank=True, verbose_name="فایل جواز کسب")
    tax_certificate_file = models.FileField(upload_to='store_requests/documents/', 
                                          blank=True, verbose_name="گواهی مالیاتی")
    
    # Status
    status = models.CharField(max_length=20, choices=Store.STATUS_CHOICES, 
                            default='pending', verbose_name="وضعیت")
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='reviewed_requests', verbose_name="بررسی شده توسط")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ بررسی")
    review_notes = models.TextField(blank=True, verbose_name="یادداشت‌های بررسی")
    
    # If approved, link to created store
    created_store = models.OneToOneField(Store, on_delete=models.SET_NULL, 
                                       null=True, blank=True, verbose_name="فروشگاه ایجاد شده")

    class Meta:
        db_table = 'shop_store_request'
        verbose_name = "درخواست فروشگاه"
        verbose_name_plural = "درخواست‌های فروشگاه"
        indexes = [
            models.Index(fields=['applicant']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"درخواست {self.store_name} توسط {self.applicant.username}"


class Category(TimestampedModel):
    """Hierarchical product categories per store"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='categories', verbose_name="فروشگاه")
    name = models.CharField(max_length=100, verbose_name="نام دسته‌بندی")
    slug = models.SlugField(max_length=100, blank=True)
    description = models.TextField(blank=True, verbose_name="توضیحات")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, 
                              related_name='children', verbose_name="دسته‌بندی والد")
    image = models.ImageField(upload_to='category_images/', blank=True, null=True, verbose_name="تصویر")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")
    
    # SEO
    meta_title = models.CharField(max_length=255, blank=True, verbose_name="عنوان متا")
    meta_description = models.TextField(max_length=320, blank=True, verbose_name="توضیحات متا")

    class Meta:
        db_table = 'shop_category_enhanced'
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"
        unique_together = ['store', 'slug']
        indexes = [
            models.Index(fields=['store', 'is_active']),
            models.Index(fields=['parent']),
            models.Index(fields=['sort_order']),
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
    
    def get_all_children(self):
        """Get all descendant categories"""
        children = list(self.children.filter(is_active=True))
        for child in self.children.filter(is_active=True):
            children.extend(child.get_all_children())
        return children


class ProductAttribute(TimestampedModel):
    """Product attributes definition for each store"""
    ATTRIBUTE_TYPES = [
        ('text', 'متن'),
        ('number', 'عدد'),
        ('boolean', 'بولی'),
        ('choice', 'انتخابی'),
        ('color', 'رنگ'),
        ('date', 'تاریخ'),
        ('url', 'لینک'),
        ('email', 'ایمیل'),
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
    
    # Validation rules
    min_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="حداقل مقدار")
    max_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="حداکثر مقدار")
    max_length = models.PositiveIntegerField(null=True, blank=True, verbose_name="حداکثر طول")

    class Meta:
        db_table = 'shop_product_attribute_enhanced'
        verbose_name = "ویژگی محصول"
        verbose_name_plural = "ویژگی‌های محصول"
        unique_together = ['store', 'slug']
        indexes = [
            models.Index(fields=['store', 'is_filterable']),
            models.Index(fields=['attribute_type']),
            models.Index(fields=['sort_order']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.store.name})"


class Product(TimestampedModel):
    """Enhanced product model with comprehensive features"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products', verbose_name="فروشگاه")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, 
                                related_name='products', verbose_name="دسته‌بندی")
    
    # Basic Information
    title = models.CharField(max_length=255, verbose_name="عنوان محصول")
    slug = models.SlugField(max_length=255, blank=True)
    description = models.TextField(blank=True, verbose_name="توضیحات")
    short_description = models.CharField(max_length=500, blank=True, verbose_name="توضیحات کوتاه")
    
    # Pricing
    price = models.DecimalField(max_digits=12, decimal_places=0, 
                               validators=[MinValueValidator(Decimal('0'))], verbose_name="قیمت")
    compare_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name="قیمت مقایسه")
    cost_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True, verbose_name="قیمت تمام‌شده")
    
    # Inventory Management
    sku = models.CharField(max_length=100, blank=True, verbose_name="کد محصول")
    barcode = models.CharField(max_length=100, blank=True, verbose_name="بارکد")
    stock = models.IntegerField(default=0, validators=[MinValueValidator(0)], verbose_name="موجودی")
    low_stock_threshold = models.IntegerField(default=5, verbose_name="حد کمبود موجودی")
    track_inventory = models.BooleanField(default=True, verbose_name="ردیابی موجودی")
    allow_backorders = models.BooleanField(default=False, verbose_name="اجازه پیش‌فروش")
    
    # Physical Properties
    weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="وزن (گرم)")
    length = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="طول (سانتی‌متر)")
    width = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="عرض (سانتی‌متر)")
    height = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="ارتفاع (سانتی‌متر)")
    
    # Status and Visibility
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    is_featured = models.BooleanField(default=False, verbose_name="ویژه")
    is_digital = models.BooleanField(default=False, verbose_name="دیجیتال")
    requires_shipping = models.BooleanField(default=True, verbose_name="نیاز به ارسال")
    
    # SEO Fields
    meta_title = models.CharField(max_length=255, blank=True, verbose_name="عنوان متا")
    meta_description = models.TextField(max_length=320, blank=True, verbose_name="توضیحات متا")
    focus_keyword = models.CharField(max_length=100, blank=True, verbose_name="کلمه کلیدی")
    
    # Timestamps
    published_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ انتشار")

    class Meta:
        db_table = 'shop_product_enhanced'
        verbose_name = "محصول"
        verbose_name_plural = "محصولات"
        unique_together = ['store', 'slug']
        indexes = [
            models.Index(fields=['store', 'is_active']),
            models.Index(fields=['category']),
            models.Index(fields=['is_featured']),
            models.Index(fields=['sku']),
            models.Index(fields=['published_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if not self.published_at and self.is_active:
            self.published_at = timezone.now()
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
        return self.track_inventory and self.stock <= 0 and not self.allow_backorders

    @property
    def can_purchase(self):
        return self.is_active and (not self.track_inventory or self.stock > 0 or self.allow_backorders)

    def __str__(self):
        return self.title


class ProductAttributeValue(TimestampedModel):
    """Product attribute values"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='attribute_values', verbose_name="محصول")
    attribute = models.ForeignKey(ProductAttribute, on_delete=models.CASCADE, verbose_name="ویژگی")
    value = models.TextField(verbose_name="مقدار")
    
    class Meta:
        db_table = 'shop_product_attribute_value_enhanced'
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
    """Product images with enhanced features"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images', verbose_name="محصول")
    image = models.ImageField(upload_to='product_images/', verbose_name="تصویر")
    alt_text = models.CharField(max_length=255, blank=True, verbose_name="متن جایگزین")
    is_primary = models.BooleanField(default=False, verbose_name="تصویر اصلی")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")
    
    # Image metadata
    width = models.PositiveIntegerField(null=True, blank=True, verbose_name="عرض")
    height = models.PositiveIntegerField(null=True, blank=True, verbose_name="ارتفاع")
    file_size = models.PositiveIntegerField(null=True, blank=True, verbose_name="اندازه فایل")

    class Meta:
        db_table = 'shop_product_image_enhanced'
        verbose_name = "تصویر محصول"
        verbose_name_plural = "تصاویر محصول"
        ordering = ['sort_order', 'created_at']
        indexes = [
            models.Index(fields=['product', 'is_primary']),
            models.Index(fields=['sort_order']),
        ]


class BulkImportLog(TimestampedModel):
    """Enhanced bulk import tracking"""
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
    file_size = models.BigIntegerField(verbose_name="اندازه فایل")
    status = models.CharField(max_length=20, choices=IMPORT_STATUS_CHOICES, default='processing', verbose_name="وضعیت")
    
    # Import Statistics
    total_rows = models.IntegerField(default=0, verbose_name="تعداد کل ردیف‌ها")
    processed_rows = models.IntegerField(default=0, verbose_name="ردیف‌های پردازش شده")
    successful_rows = models.IntegerField(default=0, verbose_name="ردیف‌های موفق")
    failed_rows = models.IntegerField(default=0, verbose_name="ردیف‌های ناموفق")
    
    # Created/Updated Statistics
    categories_created = models.IntegerField(default=0, verbose_name="دسته‌بندی‌های ایجاد شده")
    categories_updated = models.IntegerField(default=0, verbose_name="دسته‌بندی‌های به‌روزرسانی شده")
    products_created = models.IntegerField(default=0, verbose_name="محصولات ایجاد شده")
    products_updated = models.IntegerField(default=0, verbose_name="محصولات به‌روزرسانی شده")
    attributes_created = models.IntegerField(default=0, verbose_name="ویژگی‌های ایجاد شده")
    
    # Error and Warning Details
    error_details = models.JSONField(default=list, verbose_name="جزئیات خطا")
    warning_details = models.JSONField(default=list, verbose_name="جزئیات هشدار")
    
    # Processing times
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان شروع")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان اتمام")
    
    class Meta:
        db_table = 'shop_bulk_import_log_enhanced'
        verbose_name = "لاگ ایمپورت گروهی"
        verbose_name_plural = "لاگ‌های ایمپورت گروهی"
        indexes = [
            models.Index(fields=['store', 'created_at']),
            models.Index(fields=['user']),
            models.Index(fields=['status']),
        ]

    @property
    def duration_seconds(self):
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def success_rate(self):
        if self.total_rows > 0:
            return round((self.successful_rows / self.total_rows) * 100, 2)
        return 0

    def __str__(self):
        return f"Import {self.filename} - {self.status} ({self.success_rate}%)"
