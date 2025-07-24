from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import uuid


class CustomerProfile(models.Model):
    """Enhanced customer profile with additional Iranian market features"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    phone = models.CharField(max_length=15, unique=True, verbose_name='شماره تلفن')
    national_id = models.CharField(max_length=10, blank=True, null=True, verbose_name='کد ملی')
    birth_date = models.DateField(blank=True, null=True, verbose_name='تاریخ تولد')
    gender = models.CharField(
        max_length=1, 
        choices=[('M', 'مرد'), ('F', 'زن')], 
        blank=True, 
        null=True,
        verbose_name='جنسیت'
    )
    
    # Address Information
    province = models.CharField(max_length=50, blank=True, verbose_name='استان')
    city = models.CharField(max_length=50, blank=True, verbose_name='شهر')
    address = models.TextField(blank=True, verbose_name='آدرس')
    postal_code = models.CharField(max_length=10, blank=True, verbose_name='کد پستی')
    
    # Wallet & Points
    wallet_balance = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='موجودی کیف پول')
    loyalty_points = models.PositiveIntegerField(default=0, verbose_name='امتیاز وفاداری')
    
    # Preferences
    sms_notifications = models.BooleanField(default=True, verbose_name='اطلاع‌رسانی پیامکی')
    email_notifications = models.BooleanField(default=True, verbose_name='اطلاع‌رسانی ایمیل')
    marketing_notifications = models.BooleanField(default=True, verbose_name='پیام‌های تبلیغاتی')
    
    # Verification
    phone_verified = models.BooleanField(default=False, verbose_name='تلفن تایید شده')
    email_verified = models.BooleanField(default=False, verbose_name='ایمیل تایید شده')
    
    # Metadata
    registration_date = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت‌نام')
    last_login = models.DateTimeField(blank=True, null=True, verbose_name='آخرین ورود')
    total_orders = models.PositiveIntegerField(default=0, verbose_name='تعداد سفارش‌ها')
    total_spent = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name='مجموع خرید')
    
    # Customer Status
    STATUS_CHOICES = [
        ('BRONZE', 'برنزی'),
        ('SILVER', 'نقره‌ای'),
        ('GOLD', 'طلایی'),
        ('PLATINUM', 'پلاتینی'),
        ('VIP', 'ویژه')
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='BRONZE', verbose_name='سطح مشتری')
    
    # Store affiliation for multi-tenant support
    favorite_stores = models.ManyToManyField('shop.Store', blank=True, related_name='favorite_customers')
    
    class Meta:
        verbose_name = 'پروفایل مشتری'
        verbose_name_plural = 'پروفایل‌های مشتری'
        db_table = 'customer_profiles'
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.phone}"
    
    def get_status_display_persian(self):
        status_map = {
            'BRONZE': 'برنزی',
            'SILVER': 'نقره‌ای', 
            'GOLD': 'طلایی',
            'PLATINUM': 'پلاتینی',
            'VIP': 'ویژه'
        }
        return status_map.get(self.status, 'برنزی')
    
    def calculate_loyalty_level(self):
        """Calculate customer loyalty level based on total spent and orders"""
        if self.total_spent >= 5000000:  # 5M Toman
            return 'VIP'
        elif self.total_spent >= 2000000:  # 2M Toman
            return 'PLATINUM'
        elif self.total_spent >= 1000000:  # 1M Toman
            return 'GOLD'
        elif self.total_spent >= 500000:   # 500K Toman
            return 'SILVER'
        else:
            return 'BRONZE'
    
    def update_status(self):
        """Update customer status based on spending"""
        new_status = self.calculate_loyalty_level()
        if new_status != self.status:
            self.status = new_status
            self.save()
    
    def add_loyalty_points(self, amount):
        """Add loyalty points based on purchase amount"""
        # 1 point per 1000 Toman spent
        points_to_add = int(amount / 1000)
        self.loyalty_points += points_to_add
        self.save()
        return points_to_add
    
    def redeem_points(self, points):
        """Redeem loyalty points for wallet credit"""
        if self.loyalty_points >= points:
            # 100 points = 10,000 Toman
            wallet_credit = points * 100
            self.loyalty_points -= points
            self.wallet_balance += wallet_credit
            self.save()
            
            # Create transaction record
            WalletTransaction.objects.create(
                customer=self,
                transaction_type='POINTS_REDEMPTION',
                amount=wallet_credit,
                description=f'استفاده از {points} امتیاز وفاداری'
            )
            return wallet_credit
        return 0


class CustomerAddress(models.Model):
    """Customer delivery addresses"""
    
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name='addresses')
    title = models.CharField(max_length=50, verbose_name='عنوان آدرس')
    recipient_name = models.CharField(max_length=100, verbose_name='نام گیرنده')
    recipient_phone = models.CharField(max_length=15, verbose_name='تلفن گیرنده')
    
    province = models.CharField(max_length=50, verbose_name='استان')
    city = models.CharField(max_length=50, verbose_name='شهر')
    district = models.CharField(max_length=100, blank=True, verbose_name='منطقه/محله')
    address = models.TextField(verbose_name='آدرس کامل')
    postal_code = models.CharField(max_length=10, verbose_name='کد پستی')
    
    latitude = models.FloatField(blank=True, null=True, verbose_name='عرض جغرافیایی')
    longitude = models.FloatField(blank=True, null=True, verbose_name='طول جغرافیایی')
    
    is_default = models.BooleanField(default=False, verbose_name='آدرس پیش‌فرض')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ بروزرسانی')
    
    class Meta:
        verbose_name = 'آدرس مشتری'
        verbose_name_plural = 'آدرس‌های مشتری'
        db_table = 'customer_addresses'
        unique_together = ['customer', 'title']
    
    def __str__(self):
        return f"{self.customer} - {self.title}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default address per customer
        if self.is_default:
            CustomerAddress.objects.filter(
                customer=self.customer, 
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class WalletTransaction(models.Model):
    """Customer wallet transactions"""
    
    TRANSACTION_TYPES = [
        ('CHARGE', 'شارژ'),
        ('PURCHASE', 'خرید'),
        ('REFUND', 'بازگشت وجه'),
        ('POINTS_REDEMPTION', 'استفاده از امتیاز'),
        ('BONUS', 'پاداش'),
        ('PENALTY', 'جریمه')
    ]
    
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name='wallet_transactions')
    transaction_id = models.UUIDField(default=uuid.uuid4, unique=True, verbose_name='شناسه تراکنش')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, verbose_name='نوع تراکنش')
    
    amount = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='مبلغ')
    balance_before = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='موجودی قبل')
    balance_after = models.DecimalField(max_digits=12, decimal_places=0, verbose_name='موجودی بعد')
    
    description = models.TextField(blank=True, verbose_name='توضیحات')
    reference_order = models.ForeignKey('shop.Order', on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ تراکنش')
    
    class Meta:
        verbose_name = 'تراکنش کیف پول'
        verbose_name_plural = 'تراکنش‌های کیف پول'
        db_table = 'wallet_transactions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.customer} - {self.get_transaction_type_display()} - {self.amount}"


class CustomerNotification(models.Model):
    """Customer notifications system"""
    
    NOTIFICATION_TYPES = [
        ('ORDER', 'سفارش'),
        ('PAYMENT', 'پرداخت'),
        ('SHIPPING', 'ارسال'),
        ('PROMOTION', 'تخفیف'),
        ('WALLET', 'کیف پول'),
        ('GENERAL', 'عمومی')
    ]
    
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, verbose_name='نوع اطلاعیه')
    
    title = models.CharField(max_length=200, verbose_name='عنوان')
    message = models.TextField(verbose_name='پیام')
    
    is_read = models.BooleanField(default=False, verbose_name='خوانده شده')
    is_sent_sms = models.BooleanField(default=False, verbose_name='پیامک ارسال شده')
    is_sent_email = models.BooleanField(default=False, verbose_name='ایمیل ارسال شده')
    
    reference_order = models.ForeignKey('shop.Order', on_delete=models.SET_NULL, null=True, blank=True)
    reference_url = models.URLField(blank=True, verbose_name='لینک مرجع')
    
    scheduled_at = models.DateTimeField(blank=True, null=True, verbose_name='زمان‌بندی ارسال')
    sent_at = models.DateTimeField(blank=True, null=True, verbose_name='زمان ارسال')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    
    class Meta:
        verbose_name = 'اطلاعیه مشتری'
        verbose_name_plural = 'اطلاعیه‌های مشتری'
        db_table = 'customer_notifications'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.customer} - {self.title}"
    
    def mark_as_read(self):
        self.is_read = True
        self.save()


class CustomerWishlist(models.Model):
    """Customer wishlist/favorites"""
    
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey('shop.Product', on_delete=models.CASCADE)
    product_instance = models.ForeignKey('shop.ProductInstance', on_delete=models.CASCADE, null=True, blank=True)
    
    added_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ افزودن')
    
    class Meta:
        verbose_name = 'لیست علاقه‌مندی'
        verbose_name_plural = 'لیست‌های علاقه‌مندی'
        db_table = 'customer_wishlist'
        unique_together = ['customer', 'product']
    
    def __str__(self):
        return f"{self.customer} - {self.product.name}"


class CustomerReview(models.Model):
    """Customer product reviews"""
    
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name='reviews')
    product = models.ForeignKey('shop.Product', on_delete=models.CASCADE, related_name='customer_reviews')
    order = models.ForeignKey('shop.Order', on_delete=models.CASCADE, null=True, blank=True)
    
    rating = models.PositiveSmallIntegerField(verbose_name='امتیاز', help_text='1 تا 5')
    title = models.CharField(max_length=200, verbose_name='عنوان نظر')
    comment = models.TextField(verbose_name='متن نظر')
    
    # Review helpfulness
    helpful_count = models.PositiveIntegerField(default=0, verbose_name='تعداد مفید')
    not_helpful_count = models.PositiveIntegerField(default=0, verbose_name='تعداد غیرمفید')
    
    is_verified_purchase = models.BooleanField(default=False, verbose_name='خرید تایید شده')
    is_approved = models.BooleanField(default=False, verbose_name='تایید شده')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ بروزرسانی')
    
    class Meta:
        verbose_name = 'نظر مشتری'
        verbose_name_plural = 'نظرات مشتری'
        db_table = 'customer_reviews'
        unique_together = ['customer', 'product', 'order']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.customer} - {self.product.name} - {self.rating}⭐"
