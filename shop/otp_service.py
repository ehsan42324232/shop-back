# OTP Service Implementation
# Complete OTP authentication system for Mall platform

import random
import string
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from django.conf import settings
from django.core.cache import cache
import requests
import logging

logger = logging.getLogger(__name__)


class OTPService:
    """OTP generation and verification service"""
    
    def __init__(self):
        self.code_length = getattr(settings, 'OTP_CODE_LENGTH', 6)
        self.expiry_minutes = getattr(settings, 'OTP_EXPIRY_MINUTES', 5)
        self.max_attempts = getattr(settings, 'OTP_MAX_ATTEMPTS', 3)
    
    def generate_otp(self, phone_number: str, purpose: str = 'login', user=None) -> dict:
        """Generate OTP code for phone number"""
        from .mall_models import OTPVerification
        
        # Generate 6-digit code
        code = ''.join(random.choices(string.digits, k=self.code_length))
        
        # Set expiry time
        expires_at = timezone.now() + timedelta(minutes=self.expiry_minutes)
        
        # Create OTP record
        otp = OTPVerification.objects.create(
            phone_number=phone_number,
            otp_code=code,
            purpose=purpose,
            expires_at=expires_at,
            user=user
        )
        
        # Send SMS
        sms_sent = self.send_otp_sms(phone_number, code, purpose)
        
        return {
            'success': True,
            'otp_id': otp.id,
            'expires_at': expires_at,
            'sms_sent': sms_sent,
            'message': 'کد تایید ارسال شد'
        }
    
    def verify_otp(self, phone_number: str, code: str, purpose: str = 'login') -> dict:
        """Verify OTP code"""
        from .mall_models import OTPVerification
        
        try:
            otp = OTPVerification.objects.filter(
                phone_number=phone_number,
                purpose=purpose,
                is_verified=False
            ).order_by('-created_at').first()
            
            if not otp:
                return {
                    'success': False,
                    'message': 'کد تایید یافت نشد'
                }
            
            success, message = otp.verify(code)
            
            return {
                'success': success,
                'message': message,
                'user': otp.user if success else None
            }
            
        except Exception as e:
            logger.error(f"OTP verification error: {str(e)}")
            return {
                'success': False,
                'message': 'خطا در تایید کد'
            }
    
    def send_otp_sms(self, phone_number: str, code: str, purpose: str) -> bool:
        """Send OTP via SMS"""
        try:
            # Get SMS provider configuration
            sms_provider = self.get_active_sms_provider()
            if not sms_provider:
                logger.error("No active SMS provider found")
                return False
            
            # Format message based on purpose
            message = self.get_otp_message(code, purpose)
            
            # Send via provider
            return self.send_via_provider(sms_provider, phone_number, message)
            
        except Exception as e:
            logger.error(f"SMS sending error: {str(e)}")
            return False
    
    def get_active_sms_provider(self):
        """Get active SMS provider"""
        from .mall_models import SMSProvider
        
        return SMSProvider.objects.filter(
            is_active=True,
            is_default=True
        ).first() or SMSProvider.objects.filter(is_active=True).first()
    
    def get_otp_message(self, code: str, purpose: str) -> str:
        """Get formatted OTP message"""
        messages = {
            'login': f'کد ورود شما: {code}\nمال - فروشگاه‌ساز',
            'register': f'کد تایید ثبت‌نام: {code}\nمال - فروشگاه‌ساز',
            'reset_password': f'کد بازیابی رمز عبور: {code}\nمال - فروشگاه‌ساز',
            'verify_phone': f'کد تایید شماره تلفن: {code}\nمال - فروشگاه‌ساز'
        }
        
        return messages.get(purpose, f'کد تایید: {code}\nمال')
    
    def send_via_provider(self, provider, phone_number: str, message: str) -> bool:
        """Send SMS via specific provider"""
        try:
            if provider.name == 'kavenegar':
                return self.send_kavenegar(provider, phone_number, message)
            elif provider.name == 'ghasedak':
                return self.send_ghasedak(provider, phone_number, message)
            # Add other providers as needed
            
            return False
            
        except Exception as e:
            logger.error(f"Provider SMS error: {str(e)}")
            return False
    
    def send_kavenegar(self, provider, phone_number: str, message: str) -> bool:
        """Send via Kavenegar"""
        try:
            url = f"{provider.api_endpoint}/sms/send.json"
            data = {
                'receptor': phone_number,
                'message': message,
                'sender': provider.sender_number or '10008663'
            }
            headers = {
                'apikey': provider.api_key
            }
            
            response = requests.post(url, data=data, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result.get('return', {}).get('status') == 200
            
        except Exception as e:
            logger.error(f"Kavenegar SMS error: {str(e)}")
            return False
    
    def send_ghasedak(self, provider, phone_number: str, message: str) -> bool:
        """Send via Ghasedak"""
        try:
            url = f"{provider.api_endpoint}/sms/send/simple"
            data = {
                'receptor': phone_number,
                'message': message,
                'linenumber': provider.sender_number
            }
            headers = {
                'apikey': provider.api_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result.get('result', {}).get('code') == 200
            
        except Exception as e:
            logger.error(f"Ghasedak SMS error: {str(e)}")
            return False


def get_or_create_user_by_phone(phone_number: str) -> User:
    """Get or create user by phone number"""
    # Try to find existing user
    user = User.objects.filter(username=phone_number).first()
    
    if not user:
        # Create new user
        user = User.objects.create_user(
            username=phone_number,
            first_name='کاربر',
            is_active=True
        )
        
        # Create user profile if needed
        from .models import Store
        # Add user profile creation logic here
    
    return user


def authenticate_with_otp(phone_number: str, otp_code: str) -> dict:
    """Complete OTP authentication flow"""
    otp_service = OTPService()
    
    # Verify OTP
    result = otp_service.verify_otp(phone_number, otp_code, 'login')
    
    if result['success']:
        # Get or create user
        user = get_or_create_user_by_phone(phone_number)
        result['user'] = user
    
    return result