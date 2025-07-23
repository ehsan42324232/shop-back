from rest_framework import serializers
from django.contrib.auth.models import User
from .auth_models import OTPVerification, PhoneUser, LoginSession
import re


class SendOTPSerializer(serializers.Serializer):
    """Serializer for sending OTP"""
    phone = serializers.CharField(max_length=17)
    purpose = serializers.ChoiceField(
        choices=OTPVerification.PURPOSE_CHOICES,
        default='login'
    )

    def validate_phone(self, value):
        """Validate Iranian phone number"""
        # Remove spaces and normalize
        phone = re.sub(r'\s+', '', value)
        phone = phone.replace('+98', '0')
        
        # Validate format
        if not re.match(r'^09\d{9}$', phone):
            raise serializers.ValidationError(
                "شماره تلفن باید به فرمت 09xxxxxxxxx باشد"
            )
        return phone


class VerifyOTPSerializer(serializers.Serializer):
    """Serializer for verifying OTP"""
    phone = serializers.CharField(max_length=17)
    otp_code = serializers.CharField(max_length=6, min_length=6)
    purpose = serializers.ChoiceField(
        choices=OTPVerification.PURPOSE_CHOICES,
        default='login'
    )

    def validate_otp_code(self, value):
        """Validate OTP code format"""
        if not value.isdigit():
            raise serializers.ValidationError("کد تایید باید عددی باشد")
        return value

    def validate_phone(self, value):
        """Validate Iranian phone number"""
        phone = re.sub(r'\s+', '', value)
        phone = phone.replace('+98', '0')
        
        if not re.match(r'^09\d{9}$', phone):
            raise serializers.ValidationError(
                "شماره تلفن باید به فرمت 09xxxxxxxxx باشد"
            )
        return phone


class RegisterUserSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    phone = serializers.CharField(max_length=17)
    otp_code = serializers.CharField(max_length=6, min_length=6, write_only=True)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = PhoneUser
        fields = [
            'phone', 'first_name', 'last_name', 'business_name', 
            'national_id', 'is_store_owner', 'otp_code', 'password'
        ]
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True}
        }

    def validate_phone(self, value):
        """Validate phone number"""
        phone = re.sub(r'\s+', '', value)
        phone = phone.replace('+98', '0')
        
        if not re.match(r'^09\d{9}$', phone):
            raise serializers.ValidationError(
                "شماره تلفن باید به فرمت 09xxxxxxxxx باشد"
            )
        
        # Check if phone already exists
        if PhoneUser.objects.filter(phone=phone).exists():
            raise serializers.ValidationError(
                "این شماره تلفن قبلاً ثبت شده است"
            )
        
        return phone

    def validate_national_id(self, value):
        """Validate Iranian national ID"""
        if value and not re.match(r'^\d{10}$', value):
            raise serializers.ValidationError(
                "کد ملی باید 10 رقم باشد"
            )
        return value

    def validate(self, attrs):
        """Validate OTP before registration"""
        phone = attrs.get('phone')
        otp_code = attrs.get('otp_code')
        
        # Verify OTP
        try:
            otp = OTPVerification.objects.get(
                phone=phone,
                purpose='register',
                is_verified=False
            )
            success, message = otp.verify(otp_code)
            if not success:
                raise serializers.ValidationError({'otp_code': message})
        except OTPVerification.DoesNotExist:
            raise serializers.ValidationError({
                'otp_code': 'کد تایید یافت نشد یا منقضی شده است'
            })
        
        return attrs

    def create(self, validated_data):
        """Create new user"""
        otp_code = validated_data.pop('otp_code')
        password = validated_data.pop('password', None)
        
        # Create phone user
        phone_user = PhoneUser.create_user(**validated_data)
        
        # Set password if provided
        if password:
            phone_user.user.set_password(password)
            phone_user.user.save()
        
        # Mark phone as verified
        phone_user.verify_phone()
        
        return phone_user


class PhoneUserSerializer(serializers.ModelSerializer):
    """Serializer for phone user profile"""
    full_name = serializers.ReadOnlyField(source='get_full_name')
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', required=False)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)

    class Meta:
        model = PhoneUser
        fields = [
            'id', 'username', 'phone', 'email', 'first_name', 'last_name', 
            'full_name', 'business_name', 'national_id', 'is_store_owner',
            'is_phone_verified', 'is_active', 'is_approved', 'date_joined',
            'created_at', 'last_login_at'
        ]
        read_only_fields = [
            'id', 'phone', 'is_phone_verified', 'is_active', 
            'is_approved', 'created_at', 'last_login_at'
        ]

    def update(self, instance, validated_data):
        """Update user profile"""
        user_data = validated_data.pop('user', {})
        
        # Update User model fields
        if user_data:
            for attr, value in user_data.items():
                setattr(instance.user, attr, value)
            instance.user.save()
        
        # Update PhoneUser fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        return instance


class LoginResponseSerializer(serializers.Serializer):
    """Serializer for login response"""
    success = serializers.BooleanField()
    message = serializers.CharField()
    user = PhoneUserSerializer(read_only=True)
    token = serializers.CharField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password"""
    current_password = serializers.CharField(required=False)
    new_password = serializers.CharField(min_length=6)
    confirm_password = serializers.CharField()

    def validate(self, attrs):
        """Validate password change"""
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        
        if new_password != confirm_password:
            raise serializers.ValidationError({
                'confirm_password': 'رمز عبور جدید و تکرار آن باید یکسان باشند'
            })
        
        return attrs

    def validate_current_password(self, value):
        """Validate current password"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('رمز عبور فعلی اشتباه است')
        return value


class SessionSerializer(serializers.ModelSerializer):
    """Serializer for login sessions"""
    user_phone = serializers.CharField(source='user.phone', read_only=True)
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = LoginSession
        fields = [
            'id', 'user_phone', 'ip_address', 'user_agent', 
            'is_active', 'is_current', 'created_at', 'last_activity'
        ]
        read_only_fields = ['id', 'created_at', 'last_activity']

    def get_is_current(self, obj):
        """Check if this is the current session"""
        request = self.context.get('request')
        if request and hasattr(request, 'session'):
            return obj.session_key == request.session.session_key
        return False
