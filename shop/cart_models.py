# Shopping Cart Models
# Models for customer shopping cart functionality

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal

from .models import Store, TimestampedModel
from .mall_models import ProductInstance

class Cart(TimestampedModel):
    """Shopping cart for customers"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40, null=True, blank=True)  # For anonymous users
    
    class Meta:
        db_table = 'shopping_cart'
        verbose_name = "سبد خرید"
        verbose_name_plural = "سبدهای خرید"
    
    def __str__(self):
        user_info = self.user.username if self.user else f"Anonymous-{self.session_key[:8]}"
        return f"سبد {user_info} - {self.store.name}"
    
    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())
    
    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.all())
    
    def clear(self):
        """Clear all items from cart"""
        self.items.all().delete()

class CartItem(TimestampedModel):
    """Individual items in shopping cart"""
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product_instance = models.ForeignKey(ProductInstance, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    class Meta:
        db_table = 'cart_item'
        verbose_name = "آیتم سبد خرید"
        verbose_name_plural = "آیتم‌های سبد خرید"
        unique_together = ['cart', 'product_instance']
    
    def __str__(self):
        return f"{self.product_instance.product.name} x {self.quantity}"
    
    @property
    def unit_price(self):
        return self.product_instance.price
    
    @property
    def total_price(self):
        return self.unit_price * self.quantity
    
    def save(self, *args, **kwargs):
        # Ensure quantity doesn't exceed stock
        if self.quantity > self.product_instance.stock_quantity:
            self.quantity = self.product_instance.stock_quantity
        super().save(*args, **kwargs)