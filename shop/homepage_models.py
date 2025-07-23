from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from .models import TimestampedModel


class ContactRequest(TimestampedModel):
    """Contact form submissions from homepage"""
    BUSINESS_TYPE_CHOICES = [
        ('clothing', 'پوشاک'),
        ('electronics', 'لوازم الکترونیکی'),
        ('home', 'لوازم خانه'),
        ('food', 'مواد غذایی'),
        ('beauty', 'زیبایی و سلامت'),
        ('books', 'کتاب و نشریات'),
        ('sports', 'ورزش و تفریح'),
        ('other', 'سایر'),
    ]
    
    STATUS_CHOICES = [
        ('new', 'جدید'),
        ('contacted', 'تماس گرفته شده'),
        ('demo_scheduled', 'دمو برنامه‌ریزی شده'),
        ('converted', 'تبدیل شده'),
        ('not_interested', 'علاقه‌مند نیست'),
        ('follow_up', 'پیگیری'),
    ]
    
    # Contact information
    name = models.CharField(max_length=255, verbose_name="نام و نام خانوادگی")
    phone_regex = RegexValidator(
        regex=r'^(\+98|0)?9\d{9}$',
        message="شماره تلفن باید به فرمت صحیح باشد"
    )
    phone = models.CharField(
        validators=[phone_regex], 
        max_length=17, 
        verbose_name="شماره تماس"
    )
    email = models.EmailField(blank=True, verbose_name="ایمیل")
    business_type = models.CharField(
        max_length=20, 
        choices=BUSINESS_TYPE_CHOICES, 
        verbose_name="نوع کسب‌وکار"
    )
    
    # Additional information
    company_name = models.CharField(max_length=255, blank=True, verbose_name="نام شرکت")
    website_url = models.URLField(blank=True, verbose_name="وب‌سایت فعلی")
    estimated_products = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        verbose_name="تعداد تخمینی محصولات"
    )
    message = models.TextField(blank=True, verbose_name="پیام")
    
    # System fields
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='new', 
        verbose_name="وضعیت"
    )
    assigned_to = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="تخصیص داده شده به"
    )
    follow_up_date = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ پیگیری")
    notes = models.TextField(blank=True, verbose_name="یادداشت‌های داخلی")
    
    # Marketing fields
    source = models.CharField(max_length=100, default='homepage', verbose_name="منبع")
    utm_source = models.CharField(max_length=100, blank=True, verbose_name="UTM Source")
    utm_medium = models.CharField(max_length=100, blank=True, verbose_name="UTM Medium")
    utm_campaign = models.CharField(max_length=100, blank=True, verbose_name="UTM Campaign")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="آدرس IP")
    user_agent = models.TextField(blank=True, verbose_name="User Agent")

    class Meta:
        db_table = 'shop_contact_request'
        verbose_name = "درخواست تماس"
        verbose_name_plural = "درخواست‌های تماس"
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['business_type']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['follow_up_date']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.get_business_type_display()} - {self.phone}"

    @property
    def formatted_phone(self):
        """Return formatted phone number"""
        phone = self.phone.replace('+98', '0').replace(' ', '')
        if len(phone) == 11:
            return f"{phone[:4]} {phone[4:7]} {phone[7:]}"
        return phone


class PlatformSettings(TimestampedModel):
    """Platform-wide settings for Mall"""
    # Contact information
    support_email = models.EmailField(default='support@mall.ir', verbose_name="ایمیل پشتیبانی")
    support_phone = models.CharField(max_length=20, default='021-12345678', verbose_name="تلفن پشتیبانی")
    
    # Homepage content
    hero_title = models.CharField(
        max_length=255, 
        default='فروشگاه آنلاین خود را امروز راه‌اندازی کنید',
        verbose_name="عنوان اصلی"
    )
    hero_subtitle = models.TextField(
        default='با پلتفرم پیشرفته مال، فروشگاه آنلاین حرفه‌ای خود را در کمتر از ۱۰ دقیقه راه‌اندازی کنید.',
        verbose_name="زیرعنوان"
    )
    
    # Statistics for homepage
    active_stores_count = models.PositiveIntegerField(default=1000, verbose_name="تعداد فروشگاه‌های فعال")
    daily_sales_amount = models.BigIntegerField(default=50000000, verbose_name="فروش روزانه (تومان)")
    customer_satisfaction = models.PositiveIntegerField(default=99, verbose_name="رضایت مشتریان (درصد)")
    years_experience = models.PositiveIntegerField(default=5, verbose_name="سال‌های تجربه")
    
    # SEO settings
    meta_title = models.CharField(max_length=255, default='مال - فروشگاه‌ساز آنلاین', verbose_name="عنوان متا")
    meta_description = models.TextField(
        max_length=320,
        default='پلتفرم مال - راه‌اندازی فروشگاه آنلاین در ایران با ویژگی‌های پیشرفته',
        verbose_name="توضیحات متا"
    )
    
    # Social media links
    telegram_url = models.URLField(blank=True, verbose_name="لینک تلگرام")
    instagram_url = models.URLField(blank=True, verbose_name="لینک اینستاگرام")
    twitter_url = models.URLField(blank=True, verbose_name="لینک توییتر")
    linkedin_url = models.URLField(blank=True, verbose_name="لینک لینکدین")
    
    # Platform status
    maintenance_mode = models.BooleanField(default=False, verbose_name="حالت تعمیر")
    maintenance_message = models.TextField(
        blank=True,
        default='سایت به دلیل بروزرسانی موقتاً در دسترس نیست.',
        verbose_name="پیام حالت تعمیر"
    )
    
    # Feature flags
    enable_registration = models.BooleanField(default=True, verbose_name="فعال کردن ثبت نام")
    enable_demo_requests = models.BooleanField(default=True, verbose_name="فعال کردن درخواست دمو")
    enable_chat_support = models.BooleanField(default=True, verbose_name="فعال کردن پشتیبانی چت")

    class Meta:
        db_table = 'shop_platform_settings'
        verbose_name = "تنظیمات پلتفرم"
        verbose_name_plural = "تنظیمات پلتفرم"

    def __str__(self):
        return "تنظیمات پلتفرم مال"

    @classmethod
    def get_settings(cls):
        """Get or create platform settings"""
        settings, created = cls.objects.get_or_create(id=1)
        return settings


class Newsletter(TimestampedModel):
    """Newsletter subscriptions"""
    email = models.EmailField(unique=True, verbose_name="ایمیل")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    source = models.CharField(max_length=100, default='homepage', verbose_name="منبع")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="آدرس IP")
    
    class Meta:
        db_table = 'shop_newsletter'
        verbose_name = "خبرنامه"
        verbose_name_plural = "خبرنامه‌ها"
        ordering = ['-created_at']

    def __str__(self):
        return self.email


class FAQ(TimestampedModel):
    """Frequently Asked Questions"""
    question = models.CharField(max_length=500, verbose_name="سوال")
    answer = models.TextField(verbose_name="پاسخ")
    category = models.CharField(max_length=100, default='general', verbose_name="دسته‌بندی")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="ترتیب نمایش")
    
    class Meta:
        db_table = 'shop_faq'
        verbose_name = "سوال متداول"
        verbose_name_plural = "سوالات متداول"
        ordering = ['sort_order', 'created_at']

    def __str__(self):
        return self.question[:100]
