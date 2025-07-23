# shop/payment_models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator
import uuid
import json

class PaymentGateway(models.Model):
    """Payment Gateway Configuration"""
    
    GATEWAY_CHOICES = [
        ('zarinpal', 'زرین‌پال'),
        ('mellat', 'بانک ملت'),
        ('parsian', 'بانک پارسیان'),
        ('saman', 'بانک سامان'),
        ('pasargad', 'بانک پاسارگاد'),
        ('melli', 'بانک ملی'),
        ('tejarat', 'بانک تجارت'),
        ('sep', 'سداد الکترونیک پارس'),
        ('saderat', 'بانک صادرات'),
        ('postbank', 'پست بانک'),
    ]
    
    name = models.CharField(max_length=100, choices=GATEWAY_CHOICES, unique=True, verbose_name='نام درگاه')
    display_name = models.CharField(max_length=200, verbose_name='نام نمایشی')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    merchant_id = models.CharField(max_length=200, verbose_name='شناسه پذیرنده')
    api_key = models.CharField(max_length=500, blank=True, verbose_name='کلید API')
    secret_key = models.CharField(max_length=500, blank=True, verbose_name='کلید مخفی')
    endpoint_url = models.URLField(verbose_name='آدرس درگاه')
    callback_url = models.URLField(blank=True, verbose_name='آدرس بازگشت')
    
    # Gateway specific settings
    settings = models.JSONField(default=dict, blank=True, verbose_name='تنظیمات اضافی')
    
    # Fee structure
    fixed_fee = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name='کارمزد ثابت (ریال)')
    percentage_fee = models.DecimalField(max_digits=5, decimal_places=3, default=0, verbose_name='کارمزد درصدی')
    min_amount = models.PositiveIntegerField(default=1000, verbose_name='حداقل مبلغ (ریال)')
    max_amount = models.PositiveIntegerField(default=50000000, verbose_name='حداکثر مبلغ (ریال)')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ به‌روزرسانی')
    
    class Meta:
        verbose_name = 'درگاه پرداخت'
        verbose_name_plural = 'درگاه‌های پرداخت'
        ordering = ['display_name']
    
    def __str__(self):
        return f"{self.display_name} ({'فعال' if self.is_active else 'غیرفعال'})"
    
    def calculate_fee(self, amount):
        """Calculate gateway fee"""
        percentage_amount = (amount * self.percentage_fee) / 100
        return int(self.fixed_fee + percentage_amount)
    
    def can_process_amount(self, amount):
        """Check if gateway can process the amount"""
        return self.min_amount <= amount <= self.max_amount


class Payment(models.Model):
    """Payment Transaction Model"""
    
    STATUS_CHOICES = [
        ('pending', 'در انتظار پرداخت'),
        ('processing', 'در حال پردازش'),
        ('completed', 'پرداخت موفق'),
        ('failed', 'پرداخت ناموفق'),
        ('cancelled', 'لغو شده'),
        ('refunded', 'بازگشت داده شده'),
        ('expired', 'منقضی شده'),
    ]
    
    # Basic Information
    payment_id = models.UUIDField(default=uuid.uuid4, unique=True, verbose_name='شناسه پرداخت')
    order = models.ForeignKey('shop.Order', on_delete=models.CASCADE, related_name='payments', verbose_name='سفارش')
    gateway = models.ForeignKey(PaymentGateway, on_delete=models.PROTECT, verbose_name='درگاه پرداخت')
    
    # User Information
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='کاربر')
    customer_name = models.CharField(max_length=200, verbose_name='نام مشتری')
    customer_email = models.EmailField(blank=True, verbose_name='ایمیل مشتری')
    customer_phone = models.CharField(max_length=15, verbose_name='تلفن مشتری')
    
    # Amount Information
    original_amount = models.PositiveIntegerField(validators=[MinValueValidator(1000)], verbose_name='مبلغ اصلی (ریال)')
    gateway_fee = models.PositiveIntegerField(default=0, verbose_name='کارمزد درگاه (ریال)')
    final_amount = models.PositiveIntegerField(validators=[MinValueValidator(1000)], verbose_name='مبلغ نهایی (ریال)')
    
    # Status and Timing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='وضعیت')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')
    expires_at = models.DateTimeField(verbose_name='زمان انقضا')
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='زمان پرداخت')
    
    # Gateway Response Data
    gateway_transaction_id = models.CharField(max_length=200, blank=True, verbose_name='شناسه تراکنش درگاه')
    gateway_authority = models.CharField(max_length=200, blank=True, verbose_name='Authority درگاه')
    gateway_reference_id = models.CharField(max_length=200, blank=True, verbose_name='شماره مرجع')
    gateway_card_pan = models.CharField(max_length=20, blank=True, verbose_name='شماره کارت (4 رقم آخر)')
    
    # Request/Response Logs
    request_log = models.JSONField(default=dict, blank=True, verbose_name='لاگ درخواست')
    response_log = models.JSONField(default=dict, blank=True, verbose_name='لاگ پاسخ')
    callback_log = models.JSONField(default=dict, blank=True, verbose_name='لاگ بازگشت')
    
    # Additional Information
    description = models.TextField(blank=True, verbose_name='توضیحات')
    failure_reason = models.TextField(blank=True, verbose_name='دلیل عدم موفقیت')
    
    # Admin fields
    admin_notes = models.TextField(blank=True, verbose_name='یادداشت‌های مدیر')
    is_manual_verification = models.BooleanField(default=False, verbose_name='تایید دستی')
    
    class Meta:
        verbose_name = 'پرداخت'
        verbose_name_plural = 'پرداخت‌ها'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payment_id']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['gateway', 'status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['gateway_transaction_id']),
        ]
    
    def __str__(self):
        return f"پرداخت {self.payment_id} - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=15)
        
        if not self.gateway_fee:
            self.gateway_fee = self.gateway.calculate_fee(self.original_amount)
        
        if not self.final_amount:
            self.final_amount = self.original_amount + self.gateway_fee
            
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    @property
    def is_successful(self):
        return self.status == 'completed'
    
    @property
    def is_failed(self):
        return self.status in ['failed', 'cancelled', 'expired']
    
    @property
    def formatted_amount(self):
        """Return formatted amount in Tomans"""
        return f"{self.final_amount:,} ریال"
    
    def can_retry(self):
        """Check if payment can be retried"""
        return self.status in ['failed', 'cancelled', 'expired'] and not self.is_expired
    
    def mark_as_completed(self, gateway_data=None):
        """Mark payment as completed"""
        self.status = 'completed'
        self.paid_at = timezone.now()
        if gateway_data:
            self.gateway_reference_id = gateway_data.get('reference_id', '')
            self.gateway_card_pan = gateway_data.get('card_pan', '')
            self.callback_log = gateway_data
        self.save()
    
    def mark_as_failed(self, reason="", gateway_data=None):
        """Mark payment as failed"""
        self.status = 'failed'
        self.failure_reason = reason
        if gateway_data:
            self.callback_log = gateway_data
        self.save()


class PaymentAttempt(models.Model):
    """Payment Attempt Log"""
    
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='attempts', verbose_name='پرداخت')
    attempt_number = models.PositiveIntegerField(verbose_name='شماره تلاش')
    gateway_response = models.JSONField(verbose_name='پاسخ درگاه')
    status_code = models.CharField(max_length=10, verbose_name='کد وضعیت')
    message = models.TextField(verbose_name='پیام')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='زمان تلاش')
    
    class Meta:
        verbose_name = 'تلاش پرداخت'
        verbose_name_plural = 'تلاش‌های پرداخت'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"تلاش {self.attempt_number} - پرداخت {self.payment.payment_id}"


class Refund(models.Model):
    """Payment Refund Model"""
    
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('processing', 'در حال پردازش'),
        ('completed', 'تکمیل شده'),
        ('failed', 'ناموفق'),
        ('cancelled', 'لغو شده'),
    ]
    
    refund_id = models.UUIDField(default=uuid.uuid4, unique=True, verbose_name='شناسه بازگشت')
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='refunds', verbose_name='پرداخت')
    
    # Refund Information
    amount = models.PositiveIntegerField(verbose_name='مبلغ بازگشتی (ریال)')
    reason = models.TextField(verbose_name='دلیل بازگشت')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='وضعیت')
    
    # Gateway Information
    gateway_refund_id = models.CharField(max_length=200, blank=True, verbose_name='شناسه بازگشت درگاه')
    gateway_response = models.JSONField(default=dict, blank=True, verbose_name='پاسخ درگاه')
    
    # Timing
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='درخواست‌کننده')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ درخواست')
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ پردازش')
    
    # Admin fields
    admin_notes = models.TextField(blank=True, verbose_name='یادداشت‌های مدیر')
    
    class Meta:
        verbose_name = 'بازگشت وجه'
        verbose_name_plural = 'بازگشت‌های وجه'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"بازگشت {self.refund_id} - {self.amount:,} ریال"
    
    @property
    def formatted_amount(self):
        return f"{self.amount:,} ریال"


class PaymentSettings(models.Model):
    """Global Payment Settings"""
    
    # General Settings
    payment_timeout_minutes = models.PositiveIntegerField(default=15, verbose_name='مهلت پرداخت (دقیقه)')
    retry_attempts = models.PositiveIntegerField(default=3, verbose_name='تعداد تلاش مجدد')
    
    # Default Gateway
    default_gateway = models.ForeignKey(PaymentGateway, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='درگاه پیش‌فرض')
    
    # Notification Settings
    send_sms_notifications = models.BooleanField(default=True, verbose_name='ارسال پیامک')
    send_email_notifications = models.BooleanField(default=False, verbose_name='ارسال ایمیل')
    
    # Admin Settings
    require_admin_approval_amount = models.PositiveIntegerField(default=10000000, verbose_name='مبلغ نیازمند تایید مدیر (ریال)')
    auto_refund_enabled = models.BooleanField(default=False, verbose_name='بازگشت خودکار فعال')
    
    # Logging
    log_all_transactions = models.BooleanField(default=True, verbose_name='ثبت تمام تراکنش‌ها')
    log_retention_days = models.PositiveIntegerField(default=365, verbose_name='مدت نگهداری لاگ (روز)')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ به‌روزرسانی')
    
    class Meta:
        verbose_name = 'تنظیمات پرداخت'
        verbose_name_plural = 'تنظیمات پرداخت'
    
    def __str__(self):
        return "تنظیمات پرداخت"
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if not self.pk and PaymentSettings.objects.exists():
            raise ValueError("تنها یک نمونه از تنظیمات پرداخت مجاز است")
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create payment settings"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
