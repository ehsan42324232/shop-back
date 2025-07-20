from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Store, Product, Category
import uuid


class SMSCampaign(models.Model):
    """SMS marketing campaigns"""
    STATUS_CHOICES = [
        ('draft', 'پیش‌نویس'),
        ('scheduled', 'زمان‌بندی شده'),
        ('sending', 'در حال ارسال'),
        ('completed', 'تکمیل شده'),
        ('cancelled', 'لغو شده'),
        ('failed', 'ناموفق'),
    ]
    
    TARGET_CHOICES = [
        ('all', 'همه مشتریان'),
        ('new', 'مشتریان جدید'),
        ('repeat', 'مشتریان دائمی'),
        ('inactive', 'مشتریان غیرفعال'),
        ('custom', 'انتخاب دستی'),
        ('product_buyers', 'خریداران محصول خاص'),
        ('category_buyers', 'خریداران دسته‌بندی خاص'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='sms_campaigns', verbose_name="فروشگاه")
    
    # Campaign details
    name = models.CharField(max_length=255, verbose_name="نام کمپین")
    message = models.TextField(max_length=160, verbose_name="متن پیام")  # SMS character limit
    target_audience = models.CharField(max_length=20, choices=TARGET_CHOICES, verbose_name="مخاطب هدف")
    
    # Targeting filters
    target_product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="محصول هدف")
    target_category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="دسته‌بندی هدف")
    custom_phone_numbers = models.JSONField(default=list, blank=True, verbose_name="شماره‌های انتخابی")
    
    # Scheduling
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="وضعیت")
    scheduled_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان ارسال")
    
    # Statistics
    total_recipients = models.PositiveIntegerField(default=0, verbose_name="تعداد گیرندگان")
    sent_count = models.PositiveIntegerField(default=0, verbose_name="تعداد ارسالی")
    delivered_count = models.PositiveIntegerField(default=0, verbose_name="تعداد تحویلی")
    failed_count = models.PositiveIntegerField(default=0, verbose_name="تعداد ناموفق")
    
    # Costs
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="هزینه تخمینی")
    actual_cost = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="هزینه واقعی")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ به‌روزرسانی")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="شروع ارسال")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="اتمام ارسال")

    class Meta:
        db_table = 'sms_campaign'
        verbose_name = "کمپین پیامکی"
        verbose_name_plural = "کمپین‌های پیامکی"
        indexes = [
            models.Index(fields=['store', 'status']),
            models.Index(fields=['scheduled_at']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.name} - {self.store.name}"

    @property
    def success_rate(self):
        if self.sent_count > 0:
            return round((self.delivered_count / self.sent_count) * 100, 2)
        return 0

    @property
    def failure_rate(self):
        if self.sent_count > 0:
            return round((self.failed_count / self.sent_count) * 100, 2)
        return 0


class SMSMessage(models.Model):
    """Individual SMS messages"""
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('sent', 'ارسال شده'),
        ('delivered', 'تحویل داده شده'),
        ('failed', 'ناموفق'),
        ('expired', 'منقضی شده'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(SMSCampaign, on_delete=models.CASCADE, related_name='messages', verbose_name="کمپین")
    
    # Recipient info
    recipient_phone = models.CharField(max_length=20, verbose_name="شماره گیرنده")
    recipient_name = models.CharField(max_length=255, blank=True, verbose_name="نام گیرنده")
    recipient_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="کاربر گیرنده")
    
    # Message details
    message_content = models.TextField(verbose_name="متن پیام")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="وضعیت")
    
    # Provider details
    provider_message_id = models.CharField(max_length=255, blank=True, verbose_name="شناسه پیام در سرویس")
    provider_response = models.JSONField(default=dict, blank=True, verbose_name="پاسخ سرویس")
    
    # Timing
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان ارسال")
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان تحویل")
    
    # Cost
    cost = models.DecimalField(max_digits=8, decimal_places=0, default=0, verbose_name="هزینه")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")

    class Meta:
        db_table = 'sms_message'
        verbose_name = "پیام پیامکی"
        verbose_name_plural = "پیام‌های پیامکی"
        indexes = [
            models.Index(fields=['campaign']),
            models.Index(fields=['recipient_phone']),
            models.Index(fields=['status']),
            models.Index(fields=['sent_at']),
        ]

    def __str__(self):
        return f"پیام به {self.recipient_phone} - {self.get_status_display()}"


class SMSTemplate(models.Model):
    """Predefined SMS templates"""
    TEMPLATE_TYPES = [
        ('welcome', 'خوش‌آمدگویی'),
        ('order_confirmation', 'تایید سفارش'),
        ('shipping_notification', 'اطلاع ارسال'),
        ('delivery_notification', 'اطلاع تحویل'),
        ('promotional', 'تبلیغاتی'),
        ('reminder', 'یادآوری'),
        ('discount', 'تخفیف'),
        ('new_product', 'محصول جدید'),
        ('custom', 'سفارشی'),
    ]
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='sms_templates', verbose_name="فروشگاه")
    name = models.CharField(max_length=255, verbose_name="نام قالب")
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES, verbose_name="نوع قالب")
    content = models.TextField(max_length=160, verbose_name="محتوای قالب")
    
    # Template variables (for personalization)
    variables = models.JSONField(default=list, help_text="متغیرهای قابل استفاده مثل {name}, {product_name}", verbose_name="متغیرها")
    
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    usage_count = models.PositiveIntegerField(default=0, verbose_name="تعداد استفاده")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ به‌روزرسانی")

    class Meta:
        db_table = 'sms_template'
        verbose_name = "قالب پیامک"
        verbose_name_plural = "قالب‌های پیامک"
        unique_together = ['store', 'name']

    def __str__(self):
        return f"{self.name} - {self.store.name}"

    def render_message(self, context=None):
        """Render template with context variables"""
        if not context:
            context = {}
        
        message = self.content
        for key, value in context.items():
            placeholder = f"{{{key}}}"
            message = message.replace(placeholder, str(value))
        
        return message


class SMSProvider(models.Model):
    """SMS service provider settings"""
    PROVIDER_CHOICES = [
        ('kavenegar', 'کاوه نگار'),
        ('ghasedak', 'قاصدک'),
        ('payamresan', 'پیام رسان'),
        ('melipayamak', 'ملی پیامک'),
        ('smsir', 'SMS.ir'),
        ('farapayamak', 'فراپیامک'),
    ]
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='sms_providers', verbose_name="فروشگاه")
    provider_name = models.CharField(max_length=20, choices=PROVIDER_CHOICES, verbose_name="نام سرویس")
    
    # Provider configuration
    api_key = models.CharField(max_length=255, verbose_name="کلید API")
    sender_number = models.CharField(max_length=20, verbose_name="شماره فرستنده")
    
    # Additional settings stored as JSON
    settings = models.JSONField(default=dict, verbose_name="تنظیمات اضافی")
    
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    is_default = models.BooleanField(default=False, verbose_name="پیش‌فرض")
    
    # Statistics
    total_sent = models.PositiveIntegerField(default=0, verbose_name="تعداد کل ارسالی")
    total_cost = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="هزینه کل")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ به‌روزرسانی")

    class Meta:
        db_table = 'sms_provider'
        verbose_name = "سرویس پیامک"
        verbose_name_plural = "سرویس‌های پیامک"
        unique_together = ['store', 'provider_name']

    def __str__(self):
        return f"{self.get_provider_name_display()} - {self.store.name}"

    def save(self, *args, **kwargs):
        # Ensure only one default provider per store
        if self.is_default:
            SMSProvider.objects.filter(store=self.store, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class CustomerSegment(models.Model):
    """Customer segments for targeted marketing"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='customer_segments', verbose_name="فروشگاه")
    name = models.CharField(max_length=255, verbose_name="نام بخش")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    
    # Segment criteria
    criteria = models.JSONField(default=dict, verbose_name="معیارهای بخش‌بندی")
    
    # Cached customer count
    customer_count = models.PositiveIntegerField(default=0, verbose_name="تعداد مشتریان")
    last_updated = models.DateTimeField(auto_now=True, verbose_name="آخرین به‌روزرسانی")
    
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")

    class Meta:
        db_table = 'customer_segment'
        verbose_name = "بخش مشتری"
        verbose_name_plural = "بخش‌های مشتری"
        unique_together = ['store', 'name']

    def __str__(self):
        return f"{self.name} - {self.store.name}"

    def get_customers(self):
        """Get customers matching this segment criteria"""
        # This would implement the logic to filter customers based on criteria
        # For now, return empty queryset
        return User.objects.none()

    def update_customer_count(self):
        """Update cached customer count"""
        self.customer_count = self.get_customers().count()
        self.save()
