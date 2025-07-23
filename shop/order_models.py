from django.db import models
from .models import TimestampedModel, Store, Product
from django.contrib.auth.models import User

class Order(TimestampedModel):
    """Order model for Mall platform"""
    
    ORDER_STATUS_CHOICES = [
        ('pending', 'در انتظار تایید'),
        ('confirmed', 'تایید شده'),
        ('processing', 'در حال آماده‌سازی'),
        ('shipped', 'ارسال شده'),
        ('delivered', 'تحویل داده شده'),
        ('cancelled', 'لغو شده'),
        ('returned', 'مرجوع شده'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'در انتظار پرداخت'),
        ('paid', 'پرداخت شده'),
        ('failed', 'پرداخت ناموفق'),
        ('refunded', 'بازگشت داده شده'),
    ]
    
    # Basic information
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='orders', verbose_name="فروشگاه")
    order_number = models.CharField(max_length=50, unique=True, verbose_name="شماره سفارش")
    
    # Customer information
    customer_name = models.CharField(max_length=100, verbose_name="نام مشتری")
    customer_phone = models.CharField(max_length=20, verbose_name="شماره تماس")
    customer_email = models.EmailField(blank=True, verbose_name="ایمیل")
    customer_address = models.TextField(verbose_name="آدرس تحویل")
    customer_city = models.CharField(max_length=50, verbose_name="شهر")
    customer_postal_code = models.CharField(max_length=20, blank=True, verbose_name="کد پستی")
    
    # Order details
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending', verbose_name="وضعیت سفارش")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending', verbose_name="وضعیت پرداخت")
    
    # Pricing
    subtotal = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="جمع کل")
    shipping_cost = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="هزینه ارسال")
    tax_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="مالیات")
    discount_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="تخفیف")
    total_amount = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="مبلغ نهایی")
    
    # Payment information
    payment_method = models.CharField(max_length=50, blank=True, verbose_name="روش پرداخت")
    transaction_id = models.CharField(max_length=100, blank=True, verbose_name="شناسه تراکنش")
    
    # Shipping
    tracking_number = models.CharField(max_length=100, blank=True, verbose_name="کد رهگیری")
    shipping_company = models.CharField(max_length=100, blank=True, verbose_name="شرکت حمل")
    
    # Notes
    customer_notes = models.TextField(blank=True, verbose_name="یادداشت مشتری")
    admin_notes = models.TextField(blank=True, verbose_name="یادداشت مدیر")
    
    class Meta:
        db_table = 'shop_order'
        verbose_name = "سفارش"
        verbose_name_plural = "سفارشات"
        indexes = [
            models.Index(fields=['store', 'status']),
            models.Index(fields=['order_number']),
            models.Index(fields=['customer_phone']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            # Generate order number
            import uuid
            self.order_number = f"ORD-{self.store.id}-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"سفارش {self.order_number} - {self.customer_name}"

class OrderItem(TimestampedModel):
    """Order item model"""
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name="سفارش")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="محصول")
    
    # Product details at time of order
    product_title = models.CharField(max_length=255, verbose_name="نام محصول")
    product_sku = models.CharField(max_length=100, blank=True, verbose_name="کد محصول")
    unit_price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="قیمت واحد")
    quantity = models.PositiveIntegerField(verbose_name="تعداد")
    total_price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="قیمت کل")
    
    # Product attributes at time of order
    product_attributes = models.JSONField(default=dict, blank=True, verbose_name="ویژگی‌های محصول")
    
    class Meta:
        db_table = 'shop_order_item'
        verbose_name = "آیتم سفارش"
        verbose_name_plural = "آیتم‌های سفارش"
    
    def save(self, *args, **kwargs):
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.product_title} x {self.quantity}"

class Cart(TimestampedModel):
    """Shopping cart for customers"""
    
    # Customer identification (can be anonymous)
    session_key = models.CharField(max_length=40, unique=True, verbose_name="شناسه جلسه")
    customer_phone = models.CharField(max_length=20, blank=True, verbose_name="شماره تماس")
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='carts', verbose_name="فروشگاه")
    
    # Cart metadata
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    last_activity = models.DateTimeField(auto_now=True, verbose_name="آخرین فعالیت")
    
    class Meta:
        db_table = 'shop_cart'
        verbose_name = "سبد خرید"
        verbose_name_plural = "سبدهای خرید"
        indexes = [
            models.Index(fields=['session_key']),
            models.Index(fields=['store', 'is_active']),
        ]
    
    def get_total_items(self):
        return sum(item.quantity for item in self.items.all())
    
    def get_total_price(self):
        return sum(item.total_price for item in self.items.all())
    
    def __str__(self):
        return f"سبد خرید {self.session_key[:8]}"

class CartItem(TimestampedModel):
    """Cart item model"""
    
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items', verbose_name="سبد خرید")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="محصول")
    quantity = models.PositiveIntegerField(default=1, verbose_name="تعداد")
    unit_price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="قیمت واحد")
    total_price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="قیمت کل")
    
    # Selected product attributes
    selected_attributes = models.JSONField(default=dict, blank=True, verbose_name="ویژگی‌های انتخاب شده")
    
    class Meta:
        db_table = 'shop_cart_item'
        verbose_name = "آیتم سبد خرید"
        verbose_name_plural = "آیتم‌های سبد خرید"
        unique_together = ['cart', 'product']
    
    def save(self, *args, **kwargs):
        self.unit_price = self.product.price
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.product.title} x {self.quantity}"

class Customer(TimestampedModel):
    """Customer model for stores"""
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='customers', verbose_name="فروشگاه")
    phone = models.CharField(max_length=20, verbose_name="شماره تماس")
    name = models.CharField(max_length=100, verbose_name="نام")
    email = models.EmailField(blank=True, verbose_name="ایمیل")
    
    # Address information
    address = models.TextField(blank=True, verbose_name="آدرس")
    city = models.CharField(max_length=50, blank=True, verbose_name="شهر")
    postal_code = models.CharField(max_length=20, blank=True, verbose_name="کد پستی")
    
    # Customer statistics
    total_orders = models.PositiveIntegerField(default=0, verbose_name="تعداد سفارشات")
    total_spent = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="مجموع خرید")
    last_order_date = models.DateTimeField(null=True, blank=True, verbose_name="آخرین سفارش")
    
    # Marketing
    accepts_sms = models.BooleanField(default=True, verbose_name="دریافت پیامک")
    accepts_email = models.BooleanField(default=True, verbose_name="دریافت ایمیل")
    
    class Meta:
        db_table = 'shop_customer'
        verbose_name = "مشتری"
        verbose_name_plural = "مشتریان"
        unique_together = ['store', 'phone']
        indexes = [
            models.Index(fields=['store', 'phone']),
            models.Index(fields=['last_order_date']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.phone})"
