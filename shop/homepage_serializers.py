from rest_framework import serializers
from .homepage_models import ContactRequest, PlatformSettings, Newsletter, FAQ


class ContactRequestSerializer(serializers.ModelSerializer):
    """Serializer for contact form submissions"""
    
    class Meta:
        model = ContactRequest
        fields = [
            'name', 'phone', 'email', 'business_type', 
            'company_name', 'website_url', 'estimated_products', 
            'message', 'source', 'utm_source', 'utm_medium', 'utm_campaign'
        ]
        extra_kwargs = {
            'name': {'required': True},
            'phone': {'required': True},
            'business_type': {'required': True}
        }

    def validate_phone(self, value):
        """Validate phone number format"""
        import re
        phone_pattern = r'^(\+98|0)?9\d{9}$'
        if not re.match(phone_pattern, value):
            raise serializers.ValidationError(
                "شماره تلفن باید به فرمت صحیح باشد (مثال: 09123456789)"
            )
        return value

    def create(self, validated_data):
        """Create contact request with IP and user agent"""
        request = self.context.get('request')
        if request:
            # Get client IP address
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')
            validated_data['ip_address'] = ip
            
            # Get user agent
            validated_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
        
        return super().create(validated_data)


class ContactRequestAdminSerializer(serializers.ModelSerializer):
    """Serializer for admin view of contact requests"""
    formatted_phone = serializers.ReadOnlyField()
    business_type_display = serializers.CharField(source='get_business_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    
    class Meta:
        model = ContactRequest
        fields = '__all__'


class PlatformSettingsSerializer(serializers.ModelSerializer):
    """Serializer for platform settings (public view)"""
    
    class Meta:
        model = PlatformSettings
        fields = [
            'hero_title', 'hero_subtitle',
            'active_stores_count', 'daily_sales_amount', 
            'customer_satisfaction', 'years_experience',
            'meta_title', 'meta_description',
            'telegram_url', 'instagram_url', 'twitter_url', 'linkedin_url',
            'enable_registration', 'enable_demo_requests', 'enable_chat_support',
            'support_email', 'support_phone'
        ]


class NewsletterSerializer(serializers.ModelSerializer):
    """Serializer for newsletter subscriptions"""
    
    class Meta:
        model = Newsletter
        fields = ['email', 'source']
        extra_kwargs = {
            'email': {'required': True}
        }

    def validate_email(self, value):
        """Check if email is already subscribed"""
        if Newsletter.objects.filter(email=value, is_active=True).exists():
            raise serializers.ValidationError("این ایمیل قبلاً در خبرنامه ثبت شده است.")
        return value

    def create(self, validated_data):
        """Create newsletter subscription with IP"""
        request = self.context.get('request')
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')
            validated_data['ip_address'] = ip
        
        return super().create(validated_data)


class FAQSerializer(serializers.ModelSerializer):
    """Serializer for FAQ"""
    
    class Meta:
        model = FAQ
        fields = ['id', 'question', 'answer', 'category']


class PlatformStatsSerializer(serializers.Serializer):
    """Serializer for platform statistics"""
    active_stores = serializers.IntegerField()
    daily_sales = serializers.CharField()  # Formatted currency
    customer_satisfaction = serializers.CharField()  # With % sign
    years_experience = serializers.CharField()  # With + sign
    
    def to_representation(self, instance):
        """Format the statistics for display"""
        settings = PlatformSettings.get_settings()
        
        # Format daily sales
        daily_sales = settings.daily_sales_amount
        if daily_sales >= 1000000:
            daily_sales_formatted = f"{daily_sales // 1000000} میلیون تومان"
        elif daily_sales >= 1000:
            daily_sales_formatted = f"{daily_sales // 1000} هزار تومان"
        else:
            daily_sales_formatted = f"{daily_sales} تومان"
        
        return {
            'active_stores': f"{settings.active_stores_count:,}+",
            'daily_sales': daily_sales_formatted,
            'customer_satisfaction': f"{settings.customer_satisfaction}%",
            'years_experience': f"{settings.years_experience}+"
        }


class HealthCheckSerializer(serializers.Serializer):
    """Health check serializer"""
    status = serializers.CharField()
    timestamp = serializers.DateTimeField()
    version = serializers.CharField()
    database = serializers.CharField()
