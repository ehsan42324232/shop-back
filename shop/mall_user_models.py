# Mall Platform User Models
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


class MallUser(models.Model):
    """Extended user model for Mall platform"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='mall_profile')
    phone = models.CharField(max_length=20, unique=True, db_index=True)
    
    # User types
    is_store_owner = models.BooleanField(default=False)
    is_customer = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    
    # Store owner specific fields
    business_name = models.CharField(max_length=200, blank=True, null=True)
    business_type = models.CharField(max_length=100, blank=True)
    business_description = models.TextField(blank=True)
    business_address = models.TextField(blank=True)
    business_logo = models.ImageField(upload_to='business_logos/', blank=True, null=True)
    
    # Profile fields
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Verification status
    phone_verified = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    identity_verified = models.BooleanField(default=False)
    
    # Preferences
    language = models.CharField(max_length=10, default='fa')
    timezone = models.CharField(max_length=50, default='Asia/Tehran')
    notifications_enabled = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'mall_users'
        verbose_name = 'Mall User'
        verbose_name_plural = 'Mall Users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.phone})"
    
    def get_full_name(self):
        """Return full name"""
        return f"{self.user.first_name} {self.user.last_name}".strip() or self.phone
    
    def get_display_name(self):
        """Return display name for UI"""
        if self.user.first_name:
            return self.user.first_name
        return self.phone[-4:]  # Last 4 digits of phone
    
    def is_complete_profile(self):
        """Check if profile is complete"""
        required_fields = [
            self.user.first_name,
            self.phone,
        ]
        
        if self.is_store_owner:
            required_fields.extend([
                self.business_name,
                self.business_type
            ])
        
        return all(field for field in required_fields)
    
    def get_user_type_display(self):
        """Return user type for display"""
        if self.is_store_owner:
            return 'صاحب فروشگاه'
        elif self.is_customer:
            return 'مشتری'
        return 'کاربر'
    
    def can_create_store(self):
        """Check if user can create a store"""
        return self.is_store_owner and self.is_active and self.phone_verified
    
    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login_at = timezone.now()
        self.save(update_fields=['last_login_at'])


class OTPVerification(models.Model):
    """OTP verification records for phone authentication"""
    phone = models.CharField(max_length=20, db_index=True)
    code = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.IntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'otp_verifications'
        verbose_name = 'OTP Verification'
        verbose_name_plural = 'OTP Verifications'
        ordering = ['-created_at']
        unique_together = ['phone', 'code']
    
    def __str__(self):
        return f"OTP for {self.phone} - {self.code}"
    
    def is_expired(self):
        """Check if OTP is expired"""
        return timezone.now() > self.expires_at
    
    def is_valid(self):
        """Check if OTP is valid for verification"""
        return (
            not self.is_expired() and 
            not self.is_verified and 
            self.attempts < 5
        )
    
    def mark_verified(self):
        """Mark OTP as verified"""
        self.is_verified = True
        self.save(update_fields=['is_verified'])
    
    def increment_attempts(self):
        """Increment verification attempts"""
        self.attempts += 1
        self.save(update_fields=['attempts'])


class Store(models.Model):
    """Store model for Mall platform"""
    STORE_STATUS_CHOICES = [
        ('draft', 'پیش‌نویس'),
        ('pending', 'در انتظار تایید'),
        ('active', 'فعال'),
        ('suspended', 'معلق'),
        ('closed', 'بسته شده'),
    ]
    
    BUSINESS_TYPE_CHOICES = [
        ('clothing', 'پوشاک'),
        ('electronics', 'الکترونیک'),
        ('food', 'مواد غذایی'),
        ('cosmetics', 'آرایشی و بهداشتی'),
        ('home', 'خانه و آشپزخانه'),
        ('books', 'کتاب و لوازم التحریر'),
        ('sports', 'ورزش و سرگرمی'),
        ('automotive', 'خودرو و موتورسیکلت'),
        ('jewelry', 'طلا و جواهرات'),
        ('handicrafts', 'صنایع دستی'),
        ('other', 'سایر'),
    ]
    
    owner = models.ForeignKey(MallUser, on_delete=models.CASCADE, related_name='owned_stores')
    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=200, unique=True, db_index=True)
    description = models.TextField(blank=True)
    
    # Business information
    business_type = models.CharField(max_length=50, choices=BUSINESS_TYPE_CHOICES, default='other')
    business_license = models.CharField(max_length=100, blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    
    # Contact information
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Store appearance
    logo = models.ImageField(upload_to='store_logos/', blank=True, null=True)
    banner = models.ImageField(upload_to='store_banners/', blank=True, null=True)
    primary_color = models.CharField(max_length=7, default='#2563eb')  # Blue
    secondary_color = models.CharField(max_length=7, default='#dc2626')  # Red
    theme = models.CharField(max_length=50, default='modern')
    
    # Store settings
    status = models.CharField(max_length=20, choices=STORE_STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField(default=False)
    accepts_orders = models.BooleanField(default=True)
    min_order_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Domain settings
    custom_domain = models.CharField(max_length=200, blank=True, null=True, unique=True)
    subdomain = models.CharField(max_length=100, blank=True, null=True, unique=True)
    
    # Social media links
    instagram_url = models.URLField(blank=True)
    telegram_url = models.URLField(blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    
    # SEO fields
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.TextField(blank=True)
    
    # Statistics
    view_count = models.PositiveIntegerField(default=0)
    product_count = models.PositiveIntegerField(default=0)
    order_count = models.PositiveIntegerField(default=0)
    customer_count = models.PositiveIntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    launched_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'stores'
        verbose_name = 'Store'
        verbose_name_plural = 'Stores'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status']),
            models.Index(fields=['business_type']),
        ]
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        """Return store URL"""
        if self.custom_domain:
            return f"https://{self.custom_domain}"
        elif self.subdomain:
            return f"https://{self.subdomain}.mall.ir"
        else:
            return f"https://mall.ir/store/{self.slug}"
    
    def get_admin_url(self):
        """Return store admin URL"""
        return f"/dashboard/stores/{self.id}/"
    
    def is_active(self):
        """Check if store is active"""
        return self.status == 'active' and self.accepts_orders
    
    def can_accept_orders(self):
        """Check if store can accept orders"""
        return (
            self.status == 'active' and 
            self.accepts_orders and 
            self.owner.is_active
        )
    
    def increment_view_count(self):
        """Increment store view count"""
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    def update_product_count(self):
        """Update product count based on active products"""
        # This will be implemented when product models are created
        pass
    
    def get_primary_category(self):
        """Get store's primary category"""
        return dict(self.BUSINESS_TYPE_CHOICES).get(self.business_type, 'سایر')


class StoreTheme(models.Model):
    """Store theme customization"""
    store = models.OneToOneField(Store, on_delete=models.CASCADE, related_name='theme_settings')
    
    # Layout settings
    layout_type = models.CharField(max_length=50, default='modern')
    header_style = models.CharField(max_length=50, default='default')
    footer_style = models.CharField(max_length=50, default='default')
    product_grid_columns = models.IntegerField(default=3)
    
    # Color scheme
    primary_color = models.CharField(max_length=7, default='#2563eb')
    secondary_color = models.CharField(max_length=7, default='#dc2626')
    accent_color = models.CharField(max_length=7, default='#ffffff')
    text_color = models.CharField(max_length=7, default='#1f2937')
    background_color = models.CharField(max_length=7, default='#ffffff')
    
    # Typography
    heading_font = models.CharField(max_length=100, default='IRANSans')
    body_font = models.CharField(max_length=100, default='IRANSans')
    font_size_base = models.IntegerField(default=16)
    
    # Custom CSS
    custom_css = models.TextField(blank=True)
    custom_js = models.TextField(blank=True)
    
    # Settings
    show_search_bar = models.BooleanField(default=True)
    show_categories_menu = models.BooleanField(default=True)
    show_social_links = models.BooleanField(default=True)
    show_contact_info = models.BooleanField(default=True)
    enable_dark_mode = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'store_themes'
        verbose_name = 'Store Theme'
        verbose_name_plural = 'Store Themes'
    
    def __str__(self):
        return f"Theme for {self.store.name}"


class StoreAnalytics(models.Model):
    """Store analytics and statistics"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='analytics')
    date = models.DateField(db_index=True)
    
    # Traffic metrics
    page_views = models.PositiveIntegerField(default=0)
    unique_visitors = models.PositiveIntegerField(default=0)
    bounce_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    avg_session_duration = models.PositiveIntegerField(default=0)  # in seconds
    
    # Product metrics
    product_views = models.PositiveIntegerField(default=0)
    add_to_cart = models.PositiveIntegerField(default=0)
    cart_abandonment_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Sales metrics
    orders_count = models.PositiveIntegerField(default=0)
    orders_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Customer metrics
    new_customers = models.PositiveIntegerField(default=0)
    returning_customers = models.PositiveIntegerField(default=0)
    customer_lifetime_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'store_analytics'
        verbose_name = 'Store Analytics'
        verbose_name_plural = 'Store Analytics'
        unique_together = ['store', 'date']
        ordering = ['-date']
    
    def __str__(self):
        return f"Analytics for {self.store.name} - {self.date}"


class CustomerAddress(models.Model):
    """Customer shipping addresses"""
    ADDRESS_TYPE_CHOICES = [
        ('home', 'منزل'),
        ('work', 'محل کار'),
        ('other', 'سایر'),
    ]
    
    customer = models.ForeignKey(MallUser, on_delete=models.CASCADE, related_name='addresses')
    title = models.CharField(max_length=100)
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPE_CHOICES, default='home')
    
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Location coordinates (optional)
    latitude = models.DecimalField(max_digits=10, decimal_places=8, blank=True, null=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customer_addresses'
        verbose_name = 'Customer Address'
        verbose_name_plural = 'Customer Addresses'
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.customer.get_display_name()}"
    
    def get_full_address(self):
        """Return formatted full address"""
        return f"{self.address}, {self.city}, {self.state}, {self.postal_code}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default address per customer
        if self.is_default:
            CustomerAddress.objects.filter(
                customer=self.customer,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        
        super().save(*args, **kwargs)


class MallSettings(models.Model):
    """Global Mall platform settings"""
    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'mall_settings'
        verbose_name = 'Mall Setting'
        verbose_name_plural = 'Mall Settings'
        ordering = ['key']
    
    def __str__(self):
        return f"{self.key}: {self.value[:50]}"
    
    @classmethod
    def get_setting(cls, key, default=None):
        """Get setting value by key"""
        try:
            setting = cls.objects.get(key=key, is_active=True)
            return setting.value
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_setting(cls, key, value, description=''):
        """Set setting value"""
        setting, created = cls.objects.get_or_create(
            key=key,
            defaults={
                'value': str(value),
                'description': description
            }
        )
        if not created:
            setting.value = str(value)
            if description:
                setting.description = description
            setting.save()
        return setting
