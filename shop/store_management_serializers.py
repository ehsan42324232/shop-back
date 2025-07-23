from rest_framework import serializers
from django.utils.text import slugify
from .store_management_models import StoreRequest, StoreTheme, StoreSetting, StoreAnalytics
from .models import Store
from .auth_models import PhoneUser
import re


class StoreRequestSerializer(serializers.ModelSerializer):
    """Serializer for store creation requests"""
    
    class Meta:
        model = StoreRequest
        fields = [
            'store_name', 'store_name_en', 'subdomain', 'business_type',
            'description', 'business_license', 'national_id', 'address',
            'contact_phone', 'contact_email', 'website_url',
            'estimated_products', 'monthly_sales_estimate',
            'business_license_file', 'national_id_file'
        ]

    def validate_store_name(self, value):
        """Validate store name"""
        if len(value) < 2:
            raise serializers.ValidationError("نام فروشگاه باید حداقل 2 کاراکتر باشد")
        return value

    def validate_store_name_en(self, value):
        """Validate English store name"""
        if not re.match(r'^[a-zA-Z0-9\s-]+$', value):
            raise serializers.ValidationError("نام انگلیسی فقط می‌تواند شامل حروف انگلیسی، اعداد، فاصله و خط تیره باشد")
        return value

    def validate_subdomain(self, value):
        """Validate subdomain"""
        # Clean and format subdomain
        subdomain = slugify(value).replace('-', '')
        
        if len(subdomain) < 3:
            raise serializers.ValidationError("زیردامنه باید حداقل 3 کاراکتر باشد")
        
        if len(subdomain) > 30:
            raise serializers.ValidationError("زیردامنه نمی‌تواند بیش از 30 کاراکتر باشد")
        
        # Check if subdomain is available
        if StoreRequest.objects.filter(subdomain=subdomain).exists():
            raise serializers.ValidationError("این زیردامنه قبلاً رزرو شده است")
        
        if Store.objects.filter(domain__icontains=subdomain).exists():
            raise serializers.ValidationError("این زیردامنه قبلاً استفاده شده است")
        
        # Reserved subdomains
        reserved = ['www', 'api', 'admin', 'mail', 'ftp', 'shop', 'store', 'mall', 'support']
        if subdomain.lower() in reserved:
            raise serializers.ValidationError("این زیردامنه رزرو شده است")
        
        return subdomain

    def validate_national_id(self, value):
        """Validate Iranian national ID"""
        if not re.match(r'^\d{10}$', value):
            raise serializers.ValidationError("کد ملی باید 10 رقم باشد")
        
        # Iranian national ID validation algorithm
        check = int(value[9])
        sum_digits = sum(int(value[i]) * (10 - i) for i in range(9))
        remainder = sum_digits % 11
        
        if remainder < 2:
            if check != remainder:
                raise serializers.ValidationError("کد ملی معتبر نیست")
        else:
            if check != 11 - remainder:
                raise serializers.ValidationError("کد ملی معتبر نیست")
        
        return value

    def validate_contact_phone(self, value):
        """Validate contact phone"""
        phone_regex = r'^(\+98|0)?9\d{9}$'
        if not re.match(phone_regex, value.replace(' ', '')):
            raise serializers.ValidationError("شماره تلفن باید به فرمت 09xxxxxxxxx باشد")
        return value

    def create(self, validated_data):
        """Create store request"""
        # Get current user from context
        user = self.context['request'].user
        
        try:
            phone_user = PhoneUser.objects.get(user=user)
        except PhoneUser.DoesNotExist:
            raise serializers.ValidationError("کاربر معتبر نیست")
        
        # Auto-generate subdomain if not provided
        if not validated_data.get('subdomain') and validated_data.get('store_name_en'):
            validated_data['subdomain'] = slugify(validated_data['store_name_en']).replace('-', '')
        
        validated_data['user'] = phone_user
        return super().create(validated_data)


class StoreRequestStatusSerializer(serializers.ModelSerializer):
    """Serializer for store request status (read-only)"""
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    business_type_display = serializers.CharField(source='get_business_type_display', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = StoreRequest
        fields = [
            'id', 'store_name', 'store_name_en', 'subdomain', 'business_type',
            'business_type_display', 'status', 'status_display', 'user_name',
            'created_at', 'reviewed_at', 'rejection_reason'
        ]
        read_only_fields = '__all__'


class StoreThemeSerializer(serializers.ModelSerializer):
    """Serializer for store theme customization"""
    
    theme_name_display = serializers.CharField(source='get_theme_name_display', read_only=True)
    color_scheme_display = serializers.CharField(source='get_color_scheme_display', read_only=True)
    
    class Meta:
        model = StoreTheme
        fields = [
            'theme_name', 'theme_name_display', 'color_scheme', 'color_scheme_display',
            'primary_color', 'secondary_color', 'background_color', 'text_color',
            'layout_type', 'logo', 'banner_image', 'favicon', 'custom_css',
            'show_search', 'show_categories', 'show_cart', 'show_wishlist', 'show_reviews'
        ]

    def validate_primary_color(self, value):
        """Validate hex color format"""
        if not re.match(r'^#[0-9A-Fa-f]{6}$', value):
            raise serializers.ValidationError("رنگ باید به فرمت hex باشد (مثال: #FF0000)")
        return value

    def validate_secondary_color(self, value):
        """Validate hex color format"""
        if not re.match(r'^#[0-9A-Fa-f]{6}$', value):
            raise serializers.ValidationError("رنگ باید به فرمت hex باشد (مثال: #FF0000)")
        return value

    def validate_custom_css(self, value):
        """Basic CSS validation"""
        if value and len(value) > 10000:
            raise serializers.ValidationError("CSS سفارشی نمی‌تواند بیش از 10000 کاراکتر باشد")
        return value


class StoreSettingSerializer(serializers.ModelSerializer):
    """Serializer for store settings"""
    
    class Meta:
        model = StoreSetting
        fields = [
            'meta_title', 'meta_description', 'meta_keywords',
            'business_hours', 'free_shipping_threshold', 'shipping_cost',
            'min_order_amount', 'accept_cash_on_delivery', 'accept_online_payment',
            'email_notifications', 'sms_notifications',
            'instagram_url', 'telegram_url', 'whatsapp_number',
            'google_analytics_id'
        ]

    def validate_meta_title(self, value):
        """Validate meta title length"""
        if value and len(value) > 60:
            raise serializers.ValidationError("عنوان متا نباید بیش از 60 کاراکتر باشد")
        return value

    def validate_meta_description(self, value):
        """Validate meta description length"""
        if value and len(value) > 160:
            raise serializers.ValidationError("توضیحات متا نباید بیش از 160 کاراکتر باشد")
        return value

    def validate_whatsapp_number(self, value):
        """Validate WhatsApp number"""
        if value:
            phone_regex = r'^(\+98|0)?9\d{9}$'
            if not re.match(phone_regex, value.replace(' ', '')):
                raise serializers.ValidationError("شماره واتساپ باید به فرمت 09xxxxxxxxx باشد")
        return value


class StoreAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for store analytics"""
    
    class Meta:
        model = StoreAnalytics
        fields = [
            'date', 'page_views', 'unique_visitors', 'bounce_rate',
            'orders_count', 'revenue', 'conversion_rate',
            'products_viewed', 'products_added_to_cart'
        ]
        read_only_fields = '__all__'


class StoreBasicInfoSerializer(serializers.ModelSerializer):
    """Serializer for basic store information"""
    
    theme = StoreThemeSerializer(read_only=True)
    settings = StoreSettingSerializer(read_only=True)
    
    class Meta:
        model = Store
        fields = [
            'id', 'name', 'name_en', 'domain', 'description',
            'email', 'phone', 'address', 'logo',
            'is_active', 'is_approved', 'created_at',
            'theme', 'settings'
        ]
        read_only_fields = [
            'id', 'domain', 'is_active', 'is_approved', 'created_at'
        ]


class StoreDashboardSerializer(serializers.Serializer):
    """Serializer for store dashboard data"""
    
    # Store info
    store = StoreBasicInfoSerializer(read_only=True)
    
    # Recent analytics
    today_visitors = serializers.IntegerField()
    today_orders = serializers.IntegerField()
    today_revenue = serializers.DecimalField(max_digits=15, decimal_places=0)
    
    # This month stats
    month_visitors = serializers.IntegerField()
    month_orders = serializers.IntegerField()
    month_revenue = serializers.DecimalField(max_digits=15, decimal_places=0)
    
    # Product stats
    total_products = serializers.IntegerField()
    active_products = serializers.IntegerField()
    out_of_stock_products = serializers.IntegerField()
    
    # Recent orders
    recent_orders = serializers.ListField(read_only=True)
    
    # Chart data
    weekly_sales_chart = serializers.ListField(read_only=True)
    popular_products = serializers.ListField(read_only=True)


class StoreCreationWizardSerializer(serializers.Serializer):
    """Serializer for store creation wizard"""
    
    # Step 1: Basic Info
    store_name = serializers.CharField(max_length=255)
    store_name_en = serializers.CharField(max_length=255)
    subdomain = serializers.CharField(max_length=50)
    business_type = serializers.ChoiceField(choices=StoreRequest.BUSINESS_TYPE_CHOICES)
    description = serializers.CharField()
    
    # Step 2: Business Details
    business_license = serializers.CharField(max_length=20, required=False, allow_blank=True)
    national_id = serializers.CharField(max_length=10)
    address = serializers.CharField()
    
    # Step 3: Contact Info
    contact_phone = serializers.CharField(max_length=15)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    website_url = serializers.URLField(required=False, allow_blank=True)
    
    # Step 4: Estimates
    estimated_products = serializers.IntegerField(required=False, allow_null=True)
    monthly_sales_estimate = serializers.CharField(max_length=50, required=False, allow_blank=True)
    
    def validate(self, attrs):
        """Cross-field validation"""
        # Validate subdomain availability
        subdomain = slugify(attrs.get('subdomain', '')).replace('-', '')
        if StoreRequest.objects.filter(subdomain=subdomain).exists():
            raise serializers.ValidationError({
                'subdomain': 'این زیردامنه قبلاً رزرو شده است'
            })
        
        attrs['subdomain'] = subdomain
        return attrs
