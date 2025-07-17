from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid
from .models import Store, Product


class Basket(models.Model):
    """Shopping cart items - per store"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='basket_items', verbose_name="کاربر")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="محصول")
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], verbose_name="تعداد")
    
    # Store the price at time of adding to cart
    price_at_add = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="قیمت هنگام افزودن")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ به‌روزرسانی")

    class Meta:
        db_table = 'storefront_basket'
        verbose_name = "سبد خرید"
        verbose_name_plural = "سبدهای خرید"
        unique_together = ['user', 'product']

    def save(self, *args, **kwargs):
        if not self.price_at_add:
            self.price_at_add = self.product.price
        super().save(*args, **kwargs)

    @property
    def total_price(self):
        return self.price_at_add * self.quantity

    def __str__(self):
        return f"{self.user.username} - {self.product.title} ({self.quantity})"


class Order(models.Model):
    """Customer orders"""
    
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('confirmed', 'تایید شده'),
        ('processing', 'در حال پردازش'),
        ('shipped', 'ارسال شده'),
        ('delivered', 'تحویل داده شده'),
        ('cancelled', 'لغو شده'),
        ('refunded', 'مرجوع شده'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'در انتظار پرداخت'),
        ('paid', 'پرداخت شده'),
        ('failed', 'پرداخت ناموفق'),
        ('refunded', 'مرجوع شده'),
    ]
    
    DELIVERY_METHODS = [
        ('standard', 'ارسال عادی'),
        ('express', 'ارسال سریع'),
        ('same_day', 'ارسال همان روز'),
        ('pickup', 'تحویل حضوری'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=20, unique=True, blank=True, verbose_name="شماره سفارش")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders', verbose_name="کاربر")
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='orders', verbose_name="فروشگاه")
    
    # Order details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="وضعیت سفارش")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending', verbose_name="وضعیت پرداخت")
    
    # Pricing
    total_amount = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="مبلغ کل")
    tax_amount = models.DecimalField(max_digits=12, decimal_places=0, default=Decimal('0'), verbose_name="مبلغ مالیات")
    shipping_amount = models.DecimalField(max_digits=12, decimal_places=0, default=Decimal('0'), verbose_name="هزینه ارسال")
    discount_amount = models.DecimalField(max_digits=12, decimal_places=0, default=Decimal('0'), verbose_name="مبلغ تخفیف")
    
    # Payment information
    payment_method = models.CharField(max_length=50, blank=True, verbose_name="روش پرداخت")
    payment_id = models.CharField(max_length=255, blank=True, verbose_name="شناسه پرداخت")
    payment_gateway = models.CharField(max_length=50, blank=True, verbose_name="درگاه پرداخت")
    
    # Delivery information
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_METHODS, default='standard', verbose_name="روش تحویل")
    expected_delivery_date = models.DateField(null=True, blank=True, verbose_name="تاریخ تحویل مورد انتظار")
    tracking_number = models.CharField(max_length=100, blank=True, verbose_name="کد رهگیری")
    
    # Addresses (stored as JSON to be flexible)
    shipping_address = models.JSONField(default=dict, verbose_name="آدرس ارسال")
    billing_address = models.JSONField(default=dict, verbose_name="آدرس صورتحساب")
    
    # Customer information
    customer_name = models.CharField(max_length=255, verbose_name="نام مشتری")
    customer_phone = models.CharField(max_length=20, verbose_name="تلفن مشتری")
    customer_email = models.EmailField(blank=True, verbose_name="ایمیل مشتری")
    
    # Notes
    customer_notes = models.TextField(blank=True, verbose_name="یادداشت مشتری")
    admin_notes = models.TextField(blank=True, verbose_name="یادداشت مدیر")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ به‌روزرسانی")
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ تایید")
    shipped_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ ارسال")
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ تحویل")

    class Meta:
        db_table = 'storefront_order'
        verbose_name = "سفارش"
        verbose_name_plural = "سفارشات"
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['store']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['created_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.order_number:
            # Generate order number: ORD-YYYYMMDD-XXXXX
            from datetime import datetime
            date_str = datetime.now().strftime('%Y%m%d')
            count = Order.objects.filter(created_at__date=datetime.now().date()).count() + 1
            self.order_number = f"ORD-{date_str}-{count:05d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"سفارش {self.order_number}"

    @property
    def final_amount(self):
        """Final amount after tax, shipping and discount"""
        return self.total_amount + self.tax_amount + self.shipping_amount - self.discount_amount


class OrderItem(models.Model):
    """Items in an order"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name="سفارش")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="محصول")
    quantity = models.PositiveIntegerField(verbose_name="تعداد")
    price_at_order = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="قیمت هنگام سفارش")
    
    # Store product details at time of order
    product_title = models.CharField(max_length=255, verbose_name="عنوان محصول")
    product_sku = models.CharField(max_length=100, blank=True, verbose_name="کد محصول")
    product_attributes = models.JSONField(default=dict, verbose_name="ویژگی‌های محصول")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")

    class Meta:
        db_table = 'storefront_order_item'
        verbose_name = "آیتم سفارش"
        verbose_name_plural = "آیتم‌های سفارش"

    @property
    def total_price(self):
        return self.price_at_order * self.quantity

    def save(self, *args, **kwargs):
        if not self.product_title:
            self.product_title = self.product.title
        if not self.product_sku:
            self.product_sku = self.product.sku
        if not self.product_attributes:
            # Store current product attributes
            self.product_attributes = {
                attr_value.attribute.name: attr_value.value
                for attr_value in self.product.attribute_values.all()
            }
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order.order_number} - {self.product_title} ({self.quantity})"


class DeliveryZone(models.Model):
    """Delivery zones for each store"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='delivery_zones', verbose_name="فروشگاه")
    name = models.CharField(max_length=100, verbose_name="نام منطقه")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    
    # Delivery settings
    standard_price = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="قیمت ارسال عادی")
    express_price = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="قیمت ارسال سریع")
    same_day_price = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="قیمت ارسال همان روز")
    
    # Delivery time (in days)
    standard_days = models.PositiveIntegerField(default=3, verbose_name="روزهای ارسال عادی")
    express_days = models.PositiveIntegerField(default=1, verbose_name="روزهای ارسال سریع")
    same_day_available = models.BooleanField(default=False, verbose_name="ارسال همان روز موجود")
    
    # Free delivery threshold
    free_delivery_threshold = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="حد آستانه ارسال رایگان")
    
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")

    class Meta:
        db_table = 'storefront_delivery_zone'
        verbose_name = "منطقه تحویل"
        verbose_name_plural = "مناطق تحویل"
        unique_together = ['store', 'name']

    def __str__(self):
        return f"{self.store.name} - {self.name}"


class PaymentGateway(models.Model):
    """Payment gateway settings per store"""
    GATEWAY_CHOICES = [
        ('zarinpal', 'زرین‌پال'),
        ('mellat', 'بانک ملت'),
        ('parsian', 'بانک پارسیان'),
        ('saderat', 'بانک صادرات'),
        ('pasargad', 'بانک پاسارگاد'),
        ('saman', 'بانک سامان'),
    ]
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='payment_gateways', verbose_name="فروشگاه")
    gateway_type = models.CharField(max_length=20, choices=GATEWAY_CHOICES, verbose_name="نوع درگاه")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    
    # Gateway specific settings (stored as JSON)
    settings = models.JSONField(default=dict, verbose_name="تنظیمات درگاه")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ به‌روزرسانی")

    class Meta:
        db_table = 'storefront_payment_gateway'
        verbose_name = "درگاه پرداخت"
        verbose_name_plural = "درگاه‌های پرداخت"
        unique_together = ['store', 'gateway_type']

    def __str__(self):
        return f"{self.store.name} - {self.get_gateway_type_display()}"


class CustomerAddress(models.Model):
    """Customer saved addresses"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses', verbose_name="کاربر")
    title = models.CharField(max_length=100, verbose_name="عنوان آدرس")
    
    # Address details
    recipient_name = models.CharField(max_length=255, verbose_name="نام گیرنده")
    phone = models.CharField(max_length=20, verbose_name="تلفن")
    province = models.CharField(max_length=100, verbose_name="استان")
    city = models.CharField(max_length=100, verbose_name="شهر")
    address = models.TextField(verbose_name="آدرس")
    postal_code = models.CharField(max_length=20, verbose_name="کد پستی")
    
    is_default = models.BooleanField(default=False, verbose_name="آدرس پیش‌فرض")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")

    class Meta:
        db_table = 'storefront_customer_address'
        verbose_name = "آدرس مشتری"
        verbose_name_plural = "آدرس‌های مشتری"

    def __str__(self):
        return f"{self.user.username} - {self.title}"


class Wishlist(models.Model):
    """Customer wishlist"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist_items', verbose_name="کاربر")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="محصول")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")

    class Meta:
        db_table = 'storefront_wishlist'
        verbose_name = "لیست علاقه‌مندی"
        verbose_name_plural = "لیست‌های علاقه‌مندی"
        unique_together = ['user', 'product']

    def __str__(self):
        return f"{self.user.username} - {self.product.title}"
