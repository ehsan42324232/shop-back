from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from django.utils import timezone
from .models import TimestampedModel
from .auth_models import PhoneUser
import uuid
import os


class StoreRequest(TimestampedModel):
    """Store creation requests from users"""
    
    STATUS_CHOICES = [
        ('pending', 'در انتظار بررسی'),
        ('reviewing', 'در حال بررسی'),
        ('approved', 'تایید شده'),
        ('rejected', 'رد شده'),
        ('suspended', 'تعلیق شده'),
    ]
    
    BUSINESS_TYPE_CHOICES = [
        ('clothing', 'پوشاک'),
        ('electronics', 'لوازم الکترونیکی'),
        ('home', 'لوازم خانه'),
        ('food', 'مواد غذایی'),
        ('beauty', 'زیبایی و سلامت'),
        ('books', 'کتاب و نشریات'),
        ('sports', 'ورزش و تفریح'),
        ('automotive', 'خودرو و موتورسیکلت'),
        ('toys', 'اسباب بازی'),
        ('handmade', 'دست‌ساز'),
        ('other', 'سایر'),
    ]
    
    # Applicant information
    user = models.ForeignKey(
        PhoneUser, 
        on_delete=models.CASCADE, 
        related_name='store_requests',
        verbose_name="کاربر درخواست‌کننده"
    )
    
    # Store information
    store_name = models.CharField(max_length=255, verbose_name="نام فروشگاه")
    store_name_en = models.CharField(max_length=255, verbose_name="نام انگلیسی فروشگاه")
    subdomain = models.CharField(
        max_length=50, 
        unique=True, 
        verbose_name="زیردامنه",
        help_text="نام فروشگاه در آدرس اینترنت (yourstore.mall.ir)"
    )
    business_type = models.CharField(
        max_length=20,
        choices=BUSINESS_TYPE_CHOICES,
        verbose_name="نوع کسب‌وکار"
    )
    description = models.TextField(verbose_name="توضیحات فروشگاه")
    
    # Business details
    business_license = models.CharField(max_length=20, blank=True, verbose_name="شماره پروانه کسب")
    national_id = models.CharField(max_length=10, verbose_name="کد ملی صاحب کسب‌وکار")
    address = models.TextField(verbose_name="آدرس کسب‌وکار")
    
    # Contact information
    contact_phone = models.CharField(max_length=15, verbose_name="تلفن تماس")
    contact_email = models.EmailField(blank=True, verbose_name="ایمیل")
    website_url = models.URLField(blank=True, verbose_name="وب‌سایت فعلی")
    
    # Product information
    estimated_products = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="تعداد تخمینی محصولات"
    )
    monthly_sales_estimate = models.CharField(
        max_length=50, blank=True,
        verbose_name="تخمین فروش ماهانه"
    )
    
    # Documents
    business_license_file = models.FileField(
        upload_to='store_requests/licenses/',
        blank=True, null=True,
        verbose_name="فایل پروانه کسب"
    )
    national_id_file = models.FileField(
        upload_to='store_requests/ids/',
        blank=True, null=True,
        verbose_name="فایل کد ملی"
    )
    
    # Request status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="وضعیت درخواست"
    )
    
    # Admin fields
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_store_requests',
        verbose_name="بررسی شده توسط"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ بررسی")
    rejection_reason = models.TextField(blank=True, verbose_name="دلیل رد درخواست")
    admin_notes = models.TextField(blank=True, verbose_name="یادداشت‌های مدیر")
    
    class Meta:
        db_table = 'shop_store_request'
        verbose_name = "درخواست ایجاد فروشگاه"
        verbose_name_plural = "درخواست‌های ایجاد فروشگاه"
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['subdomain']),
        ]
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # Auto-generate subdomain if not provided
        if not self.subdomain and self.store_name_en:
            self.subdomain = slugify(self.store_name_en).replace('-', '')
        super().save(*args, **kwargs)

    def approve_request(self, admin_user):
        """Approve store request and create actual store"""
        from .models import Store  # Import here to avoid circular import
        
        # Create actual store
        store = Store.objects.create(
            owner=self.user.user,
            name=self.store_name,
            name_en=self.store_name_en,
            domain=f"{self.subdomain}.mall.ir",
            description=self.description,
            email=self.contact_email,
            phone=self.contact_phone,
            address=self.address,
            is_active=True,
            is_approved=True,
            approved_at=timezone.now()
        )
        
        # Update request status
        self.status = 'approved'
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.save()
        
        # Update user as store owner
        self.user.is_store_owner = True
        self.user.is_approved = True
        self.user.save()
        
        return store

    def reject_request(self, admin_user, reason):
        """Reject store request"""
        self.status = 'rejected'
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason
        self.save()

    def __str__(self):
        return f"{self.store_name} - {self.user.get_full_name()}"


class StoreTheme(TimestampedModel):
    """Store theme and customization options"""
    
    THEME_CHOICES = [
        ('default', 'پیش‌فرض'),
        ('modern', 'مدرن'),
        ('classic', 'کلاسیک'),
        ('minimal', 'مینیمال'),
        ('luxury', 'لوکس'),
        ('tech', 'تکنولوژی'),
        ('fashion', 'مد و پوشاک'),
        ('food', 'غذا و نوشیدنی'),
    ]
    
    COLOR_SCHEMES = [
        ('blue', 'آبی'),
        ('green', 'سبز'),
        ('red', 'قرمز'),
        ('purple', 'بنفش'),
        ('orange', 'نارنجی'),
        ('pink', 'صورتی'),
        ('dark', 'تیره'),
        ('light', 'روشن'),
    ]
    
    store = models.OneToOneField(
        'Store',
        on_delete=models.CASCADE,
        related_name='theme',
        verbose_name="فروشگاه"
    )
    
    # Theme settings
    theme_name = models.CharField(
        max_length=20,
        choices=THEME_CHOICES,
        default='default',
        verbose_name="نام قالب"
    )
    color_scheme = models.CharField(
        max_length=20,
        choices=COLOR_SCHEMES,
        default='blue',
        verbose_name="طرح رنگی"
    )
    
    # Customization
    primary_color = models.CharField(max_length=7, default='#3B82F6', verbose_name="رنگ اصلی")
    secondary_color = models.CharField(max_length=7, default='#EF4444', verbose_name="رنگ فرعی")
    background_color = models.CharField(max_length=7, default='#FFFFFF', verbose_name="رنگ پس‌زمینه")
    text_color = models.CharField(max_length=7, default='#1F2937', verbose_name="رنگ متن")
    
    # Layout options
    layout_type = models.CharField(
        max_length=20,
        choices=[
            ('grid', 'شبکه‌ای'),
            ('list', 'لیستی'),
            ('masonry', 'آجری'),
            ('carousel', 'اسلایدری'),
        ],
        default='grid',
        verbose_name="نوع چیدمان"
    )
    
    # Logo and images
    logo = models.ImageField(upload_to='store_themes/logos/', blank=True, null=True, verbose_name="لوگو")
    banner_image = models.ImageField(upload_to='store_themes/banners/', blank=True, null=True, verbose_name="تصویر بنر")
    favicon = models.ImageField(upload_to='store_themes/favicons/', blank=True, null=True, verbose_name="فاو آیکون")
    
    # Custom CSS
    custom_css = models.TextField(blank=True, verbose_name="CSS سفارشی")
    
    # Settings
    show_search = models.BooleanField(default=True, verbose_name="نمایش جستجو")
    show_categories = models.BooleanField(default=True, verbose_name="نمایش دسته‌بندی‌ها")
    show_cart = models.BooleanField(default=True, verbose_name="نمایش سبد خرید")
    show_wishlist = models.BooleanField(default=True, verbose_name="نمایش علاقه‌مندی‌ها")
    show_reviews = models.BooleanField(default=True, verbose_name="نمایش نظرات")
    
    class Meta:
        db_table = 'shop_store_theme'
        verbose_name = "قالب فروشگاه"
        verbose_name_plural = "قالب‌های فروشگاه"

    def __str__(self):
        return f"{self.store.name} - {self.get_theme_name_display()}"


class StoreSetting(TimestampedModel):
    """Store configuration and settings"""
    
    store = models.OneToOneField(
        'Store',
        on_delete=models.CASCADE,
        related_name='settings',
        verbose_name="فروشگاه"
    )
    
    # SEO Settings
    meta_title = models.CharField(max_length=255, blank=True, verbose_name="عنوان متا")
    meta_description = models.TextField(max_length=320, blank=True, verbose_name="توضیحات متا")
    meta_keywords = models.TextField(blank=True, verbose_name="کلمات کلیدی")
    
    # Business hours
    business_hours = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="ساعات کاری",
        help_text="ساعات کاری به فرمت JSON"
    )
    
    # Shipping settings
    free_shipping_threshold = models.DecimalField(
        max_digits=12, decimal_places=0,
        null=True, blank=True,
        verbose_name="حد آستانه ارسال رایگان"
    )
    shipping_cost = models.DecimalField(
        max_digits=10, decimal_places=0,
        default=0,
        verbose_name="هزینه ارسال"
    )
    
    # Order settings
    min_order_amount = models.DecimalField(
        max_digits=12, decimal_places=0,
        null=True, blank=True,
        verbose_name="حداقل مبلغ سفارش"
    )
    
    # Payment settings
    accept_cash_on_delivery = models.BooleanField(default=True, verbose_name="پذیرش پرداخت در محل")
    accept_online_payment = models.BooleanField(default=True, verbose_name="پذیرش پرداخت آنلاین")
    
    # Notification settings
    email_notifications = models.BooleanField(default=True, verbose_name="اعلان‌های ایمیل")
    sms_notifications = models.BooleanField(default=True, verbose_name="اعلان‌های پیامکی")
    
    # Social media
    instagram_url = models.URLField(blank=True, verbose_name="آدرس اینستاگرام")
    telegram_url = models.URLField(blank=True, verbose_name="آدرس تلگرام")
    whatsapp_number = models.CharField(max_length=15, blank=True, verbose_name="شماره واتساپ")
    
    # Analytics
    google_analytics_id = models.CharField(max_length=50, blank=True, verbose_name="شناسه گوگل آنالیتیکس")
    
    class Meta:
        db_table = 'shop_store_setting'
        verbose_name = "تنظیمات فروشگاه"
        verbose_name_plural = "تنظیمات فروشگاه‌ها"

    def __str__(self):
        return f"تنظیمات {self.store.name}"


class StoreAnalytics(TimestampedModel):
    """Store analytics and statistics"""
    
    store = models.ForeignKey(
        'Store',
        on_delete=models.CASCADE,
        related_name='analytics',
        verbose_name="فروشگاه"
    )
    
    # Date range
    date = models.DateField(verbose_name="تاریخ")
    
    # Traffic metrics
    page_views = models.PositiveIntegerField(default=0, verbose_name="بازدید صفحات")
    unique_visitors = models.PositiveIntegerField(default=0, verbose_name="بازدیدکنندگان منحصر به فرد")
    bounce_rate = models.DecimalField(
        max_digits=5, decimal_places=2, 
        default=0, verbose_name="نرخ پرش"
    )
    
    # Sales metrics
    orders_count = models.PositiveIntegerField(default=0, verbose_name="تعداد سفارشات")
    revenue = models.DecimalField(
        max_digits=15, decimal_places=0, 
        default=0, verbose_name="درآمد"
    )
    conversion_rate = models.DecimalField(
        max_digits=5, decimal_places=2, 
        default=0, verbose_name="نرخ تبدیل"
    )
    
    # Product metrics
    products_viewed = models.PositiveIntegerField(default=0, verbose_name="محصولات مشاهده شده")
    products_added_to_cart = models.PositiveIntegerField(default=0, verbose_name="محصولات افزوده شده به سبد")
    
    class Meta:
        db_table = 'shop_store_analytics'
        verbose_name = "آنالیز فروشگاه"
        verbose_name_plural = "آنالیز فروشگاه‌ها"
        unique_together = ['store', 'date']
        indexes = [
            models.Index(fields=['store', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.store.name} - {self.date}"
