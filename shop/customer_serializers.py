from rest_framework import serializers
from django.contrib.auth.models import User
from .customer_models import (
    CustomerProfile, CustomerAddress, WalletTransaction,
    CustomerNotification, CustomerWishlist, CustomerReview
)
from .serializers import ProductSerializer


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user information serializer"""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']
        read_only_fields = ['id', 'username']


class CustomerProfileSerializer(serializers.ModelSerializer):
    """Customer profile serializer with Persian field names"""
    
    user = UserBasicSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display_persian', read_only=True)
    total_orders_count = serializers.IntegerField(source='total_orders', read_only=True)
    
    class Meta:
        model = CustomerProfile
        fields = [
            'id', 'user', 'phone', 'national_id', 'birth_date', 'gender',
            'province', 'city', 'address', 'postal_code',
            'wallet_balance', 'loyalty_points', 'status', 'status_display',
            'sms_notifications', 'email_notifications', 'marketing_notifications',
            'phone_verified', 'email_verified', 'registration_date', 'last_login',
            'total_orders', 'total_orders_count', 'total_spent'
        ]
        read_only_fields = [
            'id', 'user', 'wallet_balance', 'loyalty_points', 'status',
            'phone_verified', 'email_verified', 'registration_date', 'last_login',
            'total_orders', 'total_spent'
        ]
    
    def validate_phone(self, value):
        """Validate Iranian phone number format"""
        import re
        
        # Remove any spaces or special characters
        phone = re.sub(r'[^\d]', '', value)
        
        # Check if it's a valid Iranian mobile number
        if not re.match(r'^09\d{9}$', phone):
            raise serializers.ValidationError('شماره تلفن باید با 09 شروع شده و 11 رقم باشد')
        
        return phone
    
    def validate_national_id(self, value):
        """Validate Iranian national ID"""
        if value:
            import re
            
            # Remove any spaces or special characters
            national_id = re.sub(r'[^\d]', '', value)
            
            if len(national_id) != 10:
                raise serializers.ValidationError('کد ملی باید 10 رقم باشد')
            
            # Simple validation (you can add more sophisticated validation)
            if len(set(national_id)) == 1:  # All digits are the same
                raise serializers.ValidationError('کد ملی نامعتبر است')
        
        return value
    
    def validate_postal_code(self, value):
        """Validate Iranian postal code"""
        if value:
            import re
            
            # Remove any spaces or special characters
            postal_code = re.sub(r'[^\d]', '', value)
            
            if not re.match(r'^\d{10}$', postal_code):
                raise serializers.ValidationError('کد پستی باید 10 رقم باشد')
        
        return value


class CustomerAddressSerializer(serializers.ModelSerializer):
    """Customer address serializer"""
    
    class Meta:
        model = CustomerAddress
        fields = [
            'id', 'title', 'recipient_name', 'recipient_phone',
            'province', 'city', 'district', 'address', 'postal_code',
            'latitude', 'longitude', 'is_default', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_recipient_phone(self, value):
        """Validate recipient phone number"""
        import re
        
        phone = re.sub(r'[^\d]', '', value)
        
        if not re.match(r'^09\d{9}$', phone):
            raise serializers.ValidationError('شماره تلفن گیرنده باید با 09 شروع شده و 11 رقم باشد')
        
        return phone
    
    def validate_postal_code(self, value):
        """Validate postal code"""
        import re
        
        postal_code = re.sub(r'[^\d]', '', value)
        
        if not re.match(r'^\d{10}$', postal_code):
            raise serializers.ValidationError('کد پستی باید 10 رقم باشد')
        
        return postal_code


class WalletTransactionSerializer(serializers.ModelSerializer):
    """Wallet transaction serializer"""
    
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    formatted_amount = serializers.SerializerMethodField()
    formatted_balance_before = serializers.SerializerMethodField()
    formatted_balance_after = serializers.SerializerMethodField()
    persian_date = serializers.SerializerMethodField()
    
    class Meta:
        model = WalletTransaction
        fields = [
            'id', 'transaction_id', 'transaction_type', 'transaction_type_display',
            'amount', 'formatted_amount', 'balance_before', 'formatted_balance_before',
            'balance_after', 'formatted_balance_after', 'description',
            'created_at', 'persian_date'
        ]
        read_only_fields = ['id', 'transaction_id', 'created_at']
    
    def get_formatted_amount(self, obj):
        """Format amount in Persian currency"""
        return f"{obj.amount:,.0f} تومان"
    
    def get_formatted_balance_before(self, obj):
        """Format balance before in Persian currency"""
        return f"{obj.balance_before:,.0f} تومان"
    
    def get_formatted_balance_after(self, obj):
        """Format balance after in Persian currency"""
        return f"{obj.balance_after:,.0f} تومان"
    
    def get_persian_date(self, obj):
        """Convert date to Persian format"""
        from datetime import datetime
        
        # Simple date conversion (you can use a proper Persian calendar library)
        return obj.created_at.strftime('%Y/%m/%d %H:%M')


class CustomerNotificationSerializer(serializers.ModelSerializer):
    """Customer notification serializer"""
    
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    persian_date = serializers.SerializerMethodField()
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomerNotification
        fields = [
            'id', 'notification_type', 'notification_type_display',
            'title', 'message', 'is_read', 'reference_url',
            'created_at', 'persian_date', 'time_ago'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_persian_date(self, obj):
        """Convert date to Persian format"""
        return obj.created_at.strftime('%Y/%m/%d %H:%M')
    
    def get_time_ago(self, obj):
        """Calculate time ago in Persian"""
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff.days > 0:
            return f"{diff.days} روز پیش"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} ساعت پیش"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} دقیقه پیش"
        else:
            return "همین الان"


class ProductBasicSerializer(serializers.ModelSerializer):
    """Basic product information for wishlist"""
    
    main_image = serializers.SerializerMethodField()
    formatted_price = serializers.SerializerMethodField()
    in_stock = serializers.SerializerMethodField()
    
    class Meta:
        model = None  # Will be set to Product model
        fields = ['id', 'name', 'price', 'formatted_price', 'main_image', 'in_stock']
    
    def get_main_image(self, obj):
        """Get main product image"""
        if hasattr(obj, 'images') and obj.images.exists():
            return obj.images.first().image.url
        return None
    
    def get_formatted_price(self, obj):
        """Format price in Persian currency"""
        return f"{obj.price:,.0f} تومان"
    
    def get_in_stock(self, obj):
        """Check if product is in stock"""
        if hasattr(obj, 'instances'):
            return obj.instances.filter(stock_quantity__gt=0).exists()
        return False


class CustomerWishlistSerializer(serializers.ModelSerializer):
    """Customer wishlist serializer"""
    
    product = ProductBasicSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    persian_date = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomerWishlist
        fields = ['id', 'product', 'product_id', 'added_at', 'persian_date']
        read_only_fields = ['id', 'added_at']
    
    def get_persian_date(self, obj):
        """Convert date to Persian format"""
        return obj.added_at.strftime('%Y/%m/%d')
    
    def validate_product_id(self, value):
        """Validate product exists"""
        from .models import Product
        
        try:
            Product.objects.get(id=value)
        except Product.DoesNotExist:
            raise serializers.ValidationError('محصول موردنظر یافت نشد')
        
        return value
    
    def create(self, validated_data):
        """Create wishlist item"""
        from .models import Product
        
        product_id = validated_data.pop('product_id')
        product = Product.objects.get(id=product_id)
        validated_data['product'] = product
        
        return super().create(validated_data)


class CustomerReviewSerializer(serializers.ModelSerializer):
    """Customer review serializer"""
    
    customer_name = serializers.CharField(source='customer.user.get_full_name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    persian_date = serializers.SerializerMethodField()
    rating_stars = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomerReview
        fields = [
            'id', 'customer_name', 'product', 'product_name', 'rating', 'rating_stars',
            'title', 'comment', 'helpful_count', 'not_helpful_count',
            'is_verified_purchase', 'is_approved', 'created_at', 'persian_date'
        ]
        read_only_fields = [
            'id', 'customer_name', 'product_name', 'helpful_count', 'not_helpful_count',
            'is_verified_purchase', 'is_approved', 'created_at'
        ]
    
    def get_persian_date(self, obj):
        """Convert date to Persian format"""
        return obj.created_at.strftime('%Y/%m/%d')
    
    def get_rating_stars(self, obj):
        """Get rating as stars"""
        return '⭐' * obj.rating + '☆' * (5 - obj.rating)
    
    def validate_rating(self, value):
        """Validate rating is between 1 and 5"""
        if not 1 <= value <= 5:
            raise serializers.ValidationError('امتیاز باید بین 1 تا 5 باشد')
        return value
    
    def validate_title(self, value):
        """Validate title length"""
        if len(value.strip()) < 5:
            raise serializers.ValidationError('عنوان نظر باید حداقل 5 کاراکتر باشد')
        return value.strip()
    
    def validate_comment(self, value):
        """Validate comment length"""
        if len(value.strip()) < 10:
            raise serializers.ValidationError('متن نظر باید حداقل 10 کاراکتر باشد')
        return value.strip()


class CustomerStatsSerializer(serializers.Serializer):
    """Customer statistics serializer"""
    
    total_orders = serializers.IntegerField()
    total_spent = serializers.DecimalField(max_digits=12, decimal_places=0)
    wallet_balance = serializers.DecimalField(max_digits=12, decimal_places=0)
    loyalty_points = serializers.IntegerField()
    wishlist_count = serializers.IntegerField()
    review_count = serializers.IntegerField()
    average_rating_given = serializers.DecimalField(max_digits=3, decimal_places=2)
    member_since = serializers.DateTimeField()
    last_order_date = serializers.DateTimeField()
    favorite_category = serializers.CharField()
    
    # Formatted fields
    formatted_total_spent = serializers.SerializerMethodField()
    formatted_wallet_balance = serializers.SerializerMethodField()
    member_since_persian = serializers.SerializerMethodField()
    last_order_persian = serializers.SerializerMethodField()
    
    def get_formatted_total_spent(self, obj):
        return f"{obj['total_spent']:,.0f} تومان"
    
    def get_formatted_wallet_balance(self, obj):
        return f"{obj['wallet_balance']:,.0f} تومان"
    
    def get_member_since_persian(self, obj):
        return obj['member_since'].strftime('%Y/%m/%d') if obj['member_since'] else ''
    
    def get_last_order_persian(self, obj):
        return obj['last_order_date'].strftime('%Y/%m/%d') if obj['last_order_date'] else ''


class CustomerOrderSummarySerializer(serializers.Serializer):
    """Customer order summary serializer"""
    
    order_id = serializers.CharField()
    order_number = serializers.CharField()
    date = serializers.DateTimeField()
    status = serializers.CharField()
    status_display = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=0)
    items_count = serializers.IntegerField()
    payment_method = serializers.CharField()
    tracking_number = serializers.CharField()
    
    # Formatted fields
    persian_date = serializers.SerializerMethodField()
    formatted_total = serializers.SerializerMethodField()
    status_class = serializers.SerializerMethodField()
    
    def get_persian_date(self, obj):
        return obj['date'].strftime('%Y/%m/%d') if obj['date'] else ''
    
    def get_formatted_total(self, obj):
        return f"{obj['total_amount']:,.0f} تومان"
    
    def get_status_class(self, obj):
        """Get CSS class for order status"""
        status_classes = {
            'PENDING': 'status-pending',
            'CONFIRMED': 'status-confirmed',
            'PROCESSING': 'status-processing',
            'SHIPPED': 'status-shipped',
            'DELIVERED': 'status-delivered',
            'CANCELLED': 'status-cancelled',
            'REFUNDED': 'status-refunded'
        }
        return status_classes.get(obj['status'], 'status-pending')


class CustomerPreferencesSerializer(serializers.ModelSerializer):
    """Customer preferences serializer"""
    
    class Meta:
        model = CustomerProfile
        fields = [
            'sms_notifications', 'email_notifications', 'marketing_notifications'
        ]
    
    def update(self, instance, validated_data):
        """Update customer preferences"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class CustomerSecuritySerializer(serializers.Serializer):
    """Customer security settings serializer"""
    
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        """Validate password change"""
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError('رمز عبور جدید و تکرار آن یکسان نیستند')
        
        # Check current password
        user = self.context['request'].user
        if not user.check_password(data['current_password']):
            raise serializers.ValidationError('رمز عبور فعلی اشتباه است')
        
        return data
    
    def save(self):
        """Save new password"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class CustomerLoyaltySerializer(serializers.Serializer):
    """Customer loyalty program serializer"""
    
    current_points = serializers.IntegerField()
    current_status = serializers.CharField()
    current_status_display = serializers.CharField()
    points_to_next_level = serializers.IntegerField()
    next_level = serializers.CharField()
    next_level_display = serializers.CharField()
    
    # Benefits
    current_benefits = serializers.ListField(child=serializers.CharField())
    next_level_benefits = serializers.ListField(child=serializers.CharField())
    
    # Points history
    points_earned_this_month = serializers.IntegerField()
    points_redeemed_this_month = serializers.IntegerField()
    
    # Conversion rates
    points_to_currency_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    currency_to_points_rate = serializers.DecimalField(max_digits=5, decimal_places=2)


# Update ProductBasicSerializer to use actual Product model
def update_product_serializer():
    """Update ProductBasicSerializer with actual Product model"""
    from .models import Product
    ProductBasicSerializer.Meta.model = Product

# Call the function to set the model
try:
    update_product_serializer()
except:
    pass  # Handle case where Product model is not yet available
