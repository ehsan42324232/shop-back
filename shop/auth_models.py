from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone
from datetime import timedelta
import random
import string


class OTPVerification(models.Model):
    """OTP verification model for phone-based authentication"""
    
    phone_regex = RegexValidator(
        regex=r'^(\+98|0)?9\d{9}$',
        message="شماره تلفن باید به فرمت صحیح باشد"
    )
    
    phone = models.CharField(
        validators=[phone_regex], 
        max_length=17, 
        verbose_name="شماره تلفن"
    )
    otp_code = models.CharField(max_length=6, verbose_name="کد تایید")
    
    # Purpose of OTP
    PURPOSE_CHOICES = [
        ('login', 'ورود'),
        ('register', 'ثبت نام'),
        ('password_reset', 'بازیابی رمز عبور'),
        ('phone_verify', 'تایید شماره تلفن'),
    ]
    purpose = models.CharField(
        max_length=20, 
        choices=PURPOSE_CHOICES, 
        default='login',
        verbose_name="هدف"
    )
    
    # Status tracking
    is_verified = models.BooleanField(default=False, verbose_name="تایید شده")
    attempts = models.PositiveIntegerField(default=0, verbose_name="تعداد تلاش")
    max_attempts = models.PositiveIntegerField(default=3, verbose_name="حداکثر تلاش")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    expires_at = models.DateTimeField(verbose_name="تاریخ انقضا")
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ تایید")
    
    # Additional data
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="آدرس IP")
    user_agent = models.TextField(blank=True, verbose_name="User Agent")
    
    class Meta:
        db_table = 'shop_otp_verification'
        verbose_name = "تایید OTP"
        verbose_name_plural = "تایید OTP ها"
        indexes = [
            models.Index(fields=['phone', 'purpose']),
            models.Index(fields=['otp_code']),
            models.Index(fields=['expires_at']),
        ]
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.expires_at:
            # OTP expires in 5 minutes
            self.expires_at = timezone.now() + timedelta(minutes=5)
        
        if not self.otp_code:
            self.otp_code = self.generate_otp()
            
        super().save(*args, **kwargs)

    def generate_otp(self):
        """Generate 6-digit OTP code"""
        return ''.join(random.choices(string.digits, k=6))

    @property
    def is_expired(self):
        """Check if OTP has expired"""
        return timezone.now() > self.expires_at

    @property
    def can_attempt(self):
        """Check if more attempts are allowed"""
        return self.attempts < self.max_attempts and not self.is_expired

    def verify(self, code):
        """Verify OTP code"""
        self.attempts += 1
        
        if self.is_expired:
            return False, "کد تایید منقضی شده است."
        
        if self.attempts > self.max_attempts:
            return False, "تعداد تلاش‌های مجاز تمام شده است."
        
        if self.otp_code == code:
            self.is_verified = True
            self.verified_at = timezone.now()
            self.save()
            return True, "کد تایید با موفقیت تایید شد."
        else:
            self.save()
            remaining = self.max_attempts - self.attempts
            return False, f"کد تایید اشتباه است. {remaining} تلاش باقی مانده."

    def __str__(self):
        return f"{self.phone} - {self.get_purpose_display()}"


class PhoneUser(models.Model):
    """Extended user model for phone-based authentication"""
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='phone_profile',
        verbose_name="کاربر"
    )
    
    phone_regex = RegexValidator(
        regex=r'^(\+98|0)?9\d{9}$',
        message="شماره تلفن باید به فرمت صحیح باشد"
    )
    
    phone = models.CharField(
        validators=[phone_regex], 
        max_length=17, 
        unique=True,
        verbose_name="شماره تلفن"
    )
    
    is_phone_verified = models.BooleanField(default=False, verbose_name="تلفن تایید شده")
    phone_verified_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ تایید تلفن")
    
    # Additional profile information
    first_name = models.CharField(max_length=50, blank=True, verbose_name="نام")
    last_name = models.CharField(max_length=50, blank=True, verbose_name="نام خانوادگی")
    
    # Business information (for store owners)
    is_store_owner = models.BooleanField(default=False, verbose_name="صاحب فروشگاه")
    business_name = models.CharField(max_length=255, blank=True, verbose_name="نام کسب‌وکار")
    national_id = models.CharField(max_length=10, blank=True, verbose_name="کد ملی")
    
    # Account status
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    is_approved = models.BooleanField(default=False, verbose_name="تایید شده")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ به‌روزرسانی")
    last_login_at = models.DateTimeField(null=True, blank=True, verbose_name="آخرین ورود")
    
    class Meta:
        db_table = 'shop_phone_user'
        verbose_name = "کاربر تلفنی"
        verbose_name_plural = "کاربران تلفنی"
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['is_store_owner']),
            models.Index(fields=['is_approved']),
        ]

    def __str__(self):
        return f"{self.get_full_name()} - {self.phone}"

    def get_full_name(self):
        """Get user's full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.user.first_name and self.user.last_name:
            return f"{self.user.first_name} {self.user.last_name}"
        else:
            return self.phone

    def verify_phone(self):
        """Mark phone as verified"""
        self.is_phone_verified = True
        self.phone_verified_at = timezone.now()
        self.save()

    @classmethod
    def create_user(cls, phone, first_name='', last_name='', **extra_fields):
        """Create a new phone user"""
        # Create Django User
        username = phone  # Use phone as username
        user = User.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            **extra_fields
        )
        
        # Create PhoneUser profile
        phone_user = cls.objects.create(
            user=user,
            phone=phone,
            first_name=first_name,
            last_name=last_name
        )
        
        return phone_user


class LoginSession(models.Model):
    """Track user login sessions"""
    
    user = models.ForeignKey(
        PhoneUser, 
        on_delete=models.CASCADE, 
        related_name='login_sessions',
        verbose_name="کاربر"
    )
    
    session_key = models.CharField(max_length=40, unique=True, verbose_name="کلید جلسه")
    ip_address = models.GenericIPAddressField(verbose_name="آدرس IP")
    user_agent = models.TextField(verbose_name="User Agent")
    
    # Session status
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    last_activity = models.DateTimeField(auto_now=True, verbose_name="آخرین فعالیت")
    expires_at = models.DateTimeField(verbose_name="تاریخ انقضا")
    
    class Meta:
        db_table = 'shop_login_session'
        verbose_name = "جلسه ورود"
        verbose_name_plural = "جلسات ورود"
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key']),
            models.Index(fields=['expires_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.expires_at:
            # Session expires in 30 days
            self.expires_at = timezone.now() + timedelta(days=30)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Check if session has expired"""
        return timezone.now() > self.expires_at

    def extend_session(self, days=30):
        """Extend session expiry"""
        self.expires_at = timezone.now() + timedelta(days=days)
        self.save()

    def __str__(self):
        return f"{self.user.phone} - {self.created_at}"
