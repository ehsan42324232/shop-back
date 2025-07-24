# Mall Platform Serializers
from rest_framework import serializers
from django.contrib.auth.models import User
from .mall_user_models import (
    MallUser, Store, StoreTheme, StoreAnalytics, 
    CustomerAddress, OTPVerification, MallSettings
)


class UserSerializer(serializers.ModelSerializer):
    """Django User serializer"""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'full_name']
        read_only_fields = ['id', 'username']
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()


class MallUserSerializer(serializers.ModelSerializer):
    """Mall User serializer"""
    user = UserSerializer(read_only=True)
    full_name = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    user_type_display = serializers.SerializerMethodField()
    is_complete_profile = serializers.SerializerMethodField()
    can_create_store = serializers.SerializerMethodField()
    
    class Meta:
        model = MallUser
        fields = [
            'id', 'user', 'phone', 'full_name', 'display_name',
            'is_store_owner', 'is_customer', 'is_active',
            'business_name', 'business_type', 'business_description',
            'avatar', 'date_of_birth', 'address', 'city', 'postal_code',
            'phone_verified', 'email_verified', 'identity_verified',
            'language', 'timezone', 'notifications_enabled',
            'sms_notifications', 'email_notifications',
            'user_type_display', 'is_complete_profile', 'can_create_store',
            'created_at', 'updated_at', 'last_login_at'
        ]
        read_only_fields = [
            'id', 'user', 'phone_verified', 'email_verified', 'identity_verified',
            'created_at', 'updated_at', 'last_login_at'
        ]
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    
    def get_display_name(self, obj):
        return obj.get_display_name()
    
    def get_user_type_display(self, obj):
        return obj.get_user_type_display()
    
    def get_is_complete_profile(self, obj):
        return obj.is_complete_profile()
    
    def get_can_create_store(self, obj):
        return obj.can_create_store()


class StoreThemeSerializer(serializers.ModelSerializer):
    """Store Theme serializer"""
    
    class Meta:
        model = StoreTheme
        exclude = ['store']


class StoreSerializer(serializers.ModelSerializer):
    """Store serializer"""
    owner = MallUserSerializer(read_only=True)
    theme_settings = StoreThemeSerializer(read_only=True)
    absolute_url = serializers.SerializerMethodField()
    admin_url = serializers.SerializerMethodField()
    is_active_status = serializers.SerializerMethodField()
    can_accept_orders_status = serializers.SerializerMethodField()
    primary_category = serializers.SerializerMethodField()
    business_type_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Store
        fields = [
            'id', 'owner', 'name', 'slug', 'description',
            'business_type', 'business_type_display', 'business_license', 'tax_id',
            'phone', 'email', 'website', 'address', 'city', 'state', 'postal_code',
            'logo', 'banner', 'primary_color', 'secondary_color', 'theme',
            'status', 'status_display', 'is_featured', 'accepts_orders', 'min_order_amount',
            'custom_domain', 'subdomain',
            'instagram_url', 'telegram_url', 'whatsapp_number',
            'meta_title', 'meta_description', 'meta_keywords',
            'view_count', 'product_count', 'order_count', 'customer_count',
            'theme_settings', 'absolute_url', 'admin_url',
            'is_active_status', 'can_accept_orders_status', 'primary_category',
            'created_at', 'updated_at', 'launched_at'
        ]
        read_only_fields = [
            'id', 'owner', 'slug', 'view_count', 'product_count', 
            'order_count', 'customer_count', 'created_at', 'updated_at'
        ]
    
    def get_absolute_url(self, obj):
        return obj.get_absolute_url()
    
    def get_admin_url(self, obj):
        return obj.get_admin_url()
    
    def get_is_active_status(self, obj):
        return obj.is_active()
    
    def get_can_accept_orders_status(self, obj):
        return obj.can_accept_orders()
    
    def get_primary_category(self, obj):
        return obj.get_primary_category()
    
    def get_business_type_display(self, obj):
        return dict(Store.BUSINESS_TYPE_CHOICES).get(obj.business_type, obj.business_type)
    
    def get_status_display(self, obj):
        return dict(Store.STORE_STATUS_CHOICES).get(obj.status, obj.status)


class StoreCreateSerializer(serializers.ModelSerializer):
    """Store creation serializer"""
    
    class Meta:
        model = Store
        fields = [
            'name', 'description', 'business_type', 'business_license',
            'phone', 'email', 'website', 'address', 'city', 'state', 'postal_code',
            'primary_color', 'secondary_color', 'theme',
            'instagram_url', 'telegram_url', 'whatsapp_number',
            'meta_title', 'meta_description', 'meta_keywords'
        ]
    
    def validate_name(self, value):
        """Validate store name"""
        from django.utils.text import slugify
        
        if len(value) < 3:
            raise serializers.ValidationError("نام فروشگاه باید حداقل ۳ کاراکتر باشد")
        
        # Check if slug already exists
        slug = slugify(value, allow_unicode=True)
        if Store.objects.filter(slug=slug).exists():
            raise serializers.ValidationError("فروشگاهی با این نام قبلاً ثبت شده است")
        
        return value
    
    def create(self, validated_data):
        """Create new store"""
        from django.utils.text import slugify
        
        # Generate unique slug
        slug = slugify(validated_data['name'], allow_unicode=True)
        counter = 1
        original_slug = slug
        
        while Store.objects.filter(slug=slug).exists():
            slug = f"{original_slug}-{counter}"
            counter += 1
        
        validated_data['slug'] = slug
        validated_data['owner'] = self.context['request'].user.mall_profile
        
        return super().create(validated_data)


class StoreAnalyticsSerializer(serializers.ModelSerializer):
    """Store Analytics serializer"""
    
    class Meta:
        model = StoreAnalytics
        exclude = ['store']


class CustomerAddressSerializer(serializers.ModelSerializer):
    """Customer Address serializer"""
    full_address = serializers.SerializerMethodField()
    address_type_display = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomerAddress
        fields = [
            'id', 'title', 'address_type', 'address_type_display',
            'full_name', 'phone', 'address', 'city', 'state', 'postal_code',
            'is_default', 'is_active', 'latitude', 'longitude',
            'full_address', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_full_address(self, obj):
        return obj.get_full_address()
    
    def get_address_type_display(self, obj):
        return dict(CustomerAddress.ADDRESS_TYPE_CHOICES).get(obj.address_type, obj.address_type)


class OTPVerificationSerializer(serializers.ModelSerializer):
    """OTP Verification serializer (for admin/debug only)"""
    is_expired_status = serializers.SerializerMethodField()
    is_valid_status = serializers.SerializerMethodField()
    
    class Meta:
        model = OTPVerification
        fields = [
            'id', 'phone', 'code', 'created_at', 'expires_at',
            'attempts', 'is_verified', 'is_expired_status', 'is_valid_status'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_is_expired_status(self, obj):
        return obj.is_expired()
    
    def get_is_valid_status(self, obj):
        return obj.is_valid()


class MallSettingsSerializer(serializers.ModelSerializer):
    """Mall Settings serializer"""
    
    class Meta:
        model = MallSettings
        fields = ['id', 'key', 'value', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


# Profile Update Serializers
class ProfileUpdateSerializer(serializers.Serializer):
    """Serializer for profile updates"""
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False)
    business_name = serializers.CharField(max_length=200, required=False)
    business_type = serializers.CharField(max_length=100, required=False)
    business_description = serializers.CharField(required=False)
    address = serializers.CharField(required=False)
    city = serializers.CharField(max_length=100, required=False)
    postal_code = serializers.CharField(max_length=20, required=False)
    language = serializers.CharField(max_length=10, required=False)
    timezone = serializers.CharField(max_length=50, required=False)
    notifications_enabled = serializers.BooleanField(required=False)
    sms_notifications = serializers.BooleanField(required=False)
    email_notifications = serializers.BooleanField(required=False)


class StoreStatsSerializer(serializers.Serializer):
    """Serializer for store statistics"""
    total_products = serializers.IntegerField()
    active_products = serializers.IntegerField()
    total_orders = serializers.IntegerField()
    pending_orders = serializers.IntegerField()
    total_customers = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    monthly_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    conversion_rate = serializers.DecimalField(max_digits=5, decimal_places=2)


class StoreDashboardSerializer(serializers.Serializer):
    """Serializer for store dashboard data"""
    store = StoreSerializer()
    stats = StoreStatsSerializer()
    recent_orders = serializers.ListField()
    top_products = serializers.ListField()
    recent_customers = serializers.ListField()


# Registration Serializers
class StoreOwnerRegistrationSerializer(serializers.Serializer):
    """Store owner registration serializer"""
    phone = serializers.CharField(max_length=20)
    name = serializers.CharField(max_length=200)
    business_name = serializers.CharField(max_length=200)
    business_type = serializers.ChoiceField(choices=Store.BUSINESS_TYPE_CHOICES, required=False)
    
    def validate_phone(self, value):
        """Validate phone number"""
        from .mall_otp_auth_views import MallOTPAuthenticationViews
        
        formatted_phone = MallOTPAuthenticationViews.format_iranian_phone(value)
        
        if not MallOTPAuthenticationViews.is_valid_iranian_phone(formatted_phone):
            raise serializers.ValidationError("شماره تلفن نامعتبر است")
        
        if MallUser.objects.filter(phone=formatted_phone).exists():
            raise serializers.ValidationError("کاربری با این شماره تلفن قبلاً ثبت نام کرده است")
        
        return formatted_phone
    
    def validate_name(self, value):
        """Validate name"""
        if len(value.strip()) < 2:
            raise serializers.ValidationError("نام باید حداقل ۲ کاراکتر باشد")
        return value.strip()
    
    def validate_business_name(self, value):
        """Validate business name"""
        if len(value.strip()) < 3:
            raise serializers.ValidationError("نام کسب‌وکار باید حداقل ۳ کاراکتر باشد")
        return value.strip()


class CustomerRegistrationSerializer(serializers.Serializer):
    """Customer registration serializer"""
    phone = serializers.CharField(max_length=20)
    name = serializers.CharField(max_length=200)
    email = serializers.EmailField(required=False, allow_blank=True)
    
    def validate_phone(self, value):
        """Validate phone number"""
        from .mall_otp_auth_views import MallOTPAuthenticationViews
        
        formatted_phone = MallOTPAuthenticationViews.format_iranian_phone(value)
        
        if not MallOTPAuthenticationViews.is_valid_iranian_phone(formatted_phone):
            raise serializers.ValidationError("شماره تلفن نامعتبر است")
        
        if MallUser.objects.filter(phone=formatted_phone).exists():
            raise serializers.ValidationError("کاربری با این شماره تلفن قبلاً ثبت نام کرده است")
        
        return formatted_phone
    
    def validate_name(self, value):
        """Validate name"""
        if len(value.strip()) < 2:
            raise serializers.ValidationError("نام باید حداقل ۲ کاراکتر باشد")
        return value.strip()


# API Response Serializers
class APIResponseSerializer(serializers.Serializer):
    """Standard API response serializer"""
    success = serializers.BooleanField()
    message = serializers.CharField()
    data = serializers.JSONField(required=False)
    errors = serializers.JSONField(required=False)


class OTPRequestSerializer(serializers.Serializer):
    """OTP request serializer"""
    phone = serializers.CharField(max_length=20)
    
    def validate_phone(self, value):
        """Validate phone number"""
        from .mall_otp_auth_views import MallOTPAuthenticationViews
        
        formatted_phone = MallOTPAuthenticationViews.format_iranian_phone(value)
        
        if not MallOTPAuthenticationViews.is_valid_iranian_phone(formatted_phone):
            raise serializers.ValidationError("شماره تلفن نامعتبر است")
        
        return formatted_phone


class OTPVerifySerializer(serializers.Serializer):
    """OTP verification serializer"""
    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=10)
    
    def validate_phone(self, value):
        """Validate phone number"""
        from .mall_otp_auth_views import MallOTPAuthenticationViews
        
        formatted_phone = MallOTPAuthenticationViews.format_iranian_phone(value)
        
        if not MallOTPAuthenticationViews.is_valid_iranian_phone(formatted_phone):
            raise serializers.ValidationError("شماره تلفن نامعتبر است")
        
        return formatted_phone
    
    def validate_code(self, value):
        """Validate OTP code"""
        code = value.strip()
        if not code.isdigit():
            raise serializers.ValidationError("کد تایید باید عددی باشد")
        
        if len(code) < 4 or len(code) > 6:
            raise serializers.ValidationError("کد تایید باید بین ۴ تا ۶ رقم باشد")
        
        return code


class TokenRefreshSerializer(serializers.Serializer):
    """Token refresh serializer"""
    refresh_token = serializers.CharField()


# Search and Filter Serializers
class StoreSearchSerializer(serializers.Serializer):
    """Store search serializer"""
    query = serializers.CharField(max_length=200, required=False, allow_blank=True)
    business_type = serializers.ChoiceField(choices=Store.BUSINESS_TYPE_CHOICES, required=False)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Store.STORE_STATUS_CHOICES, required=False)
    is_featured = serializers.BooleanField(required=False)
    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)
    ordering = serializers.ChoiceField(
        choices=[
            'name', '-name', 'created_at', '-created_at',
            'view_count', '-view_count', 'product_count', '-product_count'
        ],
        required=False,
        default='-created_at'
    )


class UserSearchSerializer(serializers.Serializer):
    """User search serializer"""
    query = serializers.CharField(max_length=200, required=False, allow_blank=True)
    user_type = serializers.ChoiceField(
        choices=[('store_owner', 'Store Owner'), ('customer', 'Customer')],
        required=False
    )
    is_active = serializers.BooleanField(required=False)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)
    ordering = serializers.ChoiceField(
        choices=[
            'user__first_name', '-user__first_name',
            'created_at', '-created_at',
            'last_login_at', '-last_login_at'
        ],
        required=False,
        default='-created_at'
    )


# Bulk Operations Serializers
class BulkStoreUpdateSerializer(serializers.Serializer):
    """Bulk store update serializer"""
    store_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    action = serializers.ChoiceField(choices=[
        'activate', 'deactivate', 'feature', 'unfeature', 'delete'
    ])


class BulkUserUpdateSerializer(serializers.Serializer):
    """Bulk user update serializer"""
    user_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    action = serializers.ChoiceField(choices=[
        'activate', 'deactivate', 'verify_phone', 'delete'
    ])


# Export Serializers
class ExportDataSerializer(serializers.Serializer):
    """Export data serializer"""
    format = serializers.ChoiceField(choices=['csv', 'excel', 'json'], default='csv')
    fields = serializers.ListField(child=serializers.CharField(), required=False)
    filters = serializers.JSONField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
