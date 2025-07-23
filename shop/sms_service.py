import requests
import logging
from django.conf import settings
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class SMSService:
    """SMS service for sending OTP codes"""
    
    def __init__(self):
        # Default SMS settings - should be configured in Django settings
        self.api_key = getattr(settings, 'SMS_API_KEY', '')
        self.sender_number = getattr(settings, 'SMS_SENDER_NUMBER', '1000596446')
        self.base_url = getattr(settings, 'SMS_BASE_URL', 'https://api.kavenegar.com/v1')
        
    def send_otp(self, phone: str, otp_code: str, purpose: str = 'login') -> Tuple[bool, str]:
        """
        Send OTP via SMS
        
        Args:
            phone: Recipient phone number
            otp_code: 6-digit OTP code
            purpose: Purpose of OTP (login, register, etc.)
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Format phone number (remove +98 prefix if exists)
            phone = phone.replace('+98', '').replace(' ', '')
            if not phone.startswith('09'):
                phone = '0' + phone
                
            # Prepare message based on purpose
            message = self._get_message_template(purpose, otp_code)
            
            # Use mock SMS in development
            if settings.DEBUG:
                return self._send_mock_sms(phone, message)
            
            # Send real SMS in production
            return self._send_real_sms(phone, message)
            
        except Exception as e:
            logger.error(f"SMS sending failed: {str(e)}")
            return False, "خطا در ارسال پیامک"
    
    def _get_message_template(self, purpose: str, otp_code: str) -> str:
        """Get SMS message template based on purpose"""
        templates = {
            'login': f"کد ورود شما به پلتفرم مال: {otp_code}\nاین کد تا 5 دقیقه معتبر است.",
            'register': f"کد تایید ثبت نام در پلتفرم مال: {otp_code}\nاین کد تا 5 دقیقه معتبر است.",
            'password_reset': f"کد بازیابی رمز عبور مال: {otp_code}\nاین کد تا 5 دقیقه معتبر است.",
            'phone_verify': f"کد تایید شماره تلفن مال: {otp_code}\nاین کد تا 5 دقیقه معتبر است.",
        }
        return templates.get(purpose, templates['login'])
    
    def _send_mock_sms(self, phone: str, message: str) -> Tuple[bool, str]:
        """Mock SMS sending for development"""
        logger.info(f"MOCK SMS to {phone}: {message}")
        print(f"📱 MOCK SMS to {phone}:")
        print(f"   {message}")
        print("-" * 50)
        return True, "پیامک با موفقیت ارسال شد (حالت توسعه)"
    
    def _send_real_sms(self, phone: str, message: str) -> Tuple[bool, str]:
        """Send real SMS using Kavenegar API"""
        if not self.api_key:
            logger.error("SMS API key not configured")
            return False, "سرویس پیامک پیکربندی نشده است"
        
        try:
            url = f"{self.base_url}/{self.api_key}/sms/send.json"
            
            data = {
                'sender': self.sender_number,
                'receptor': phone,
                'message': message
            }
            
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('return', {}).get('status') == 200:
                logger.info(f"SMS sent successfully to {phone}")
                return True, "پیامک با موفقیت ارسال شد"
            else:
                error_msg = result.get('return', {}).get('message', 'خطای نامشخص')
                logger.error(f"SMS API error: {error_msg}")
                return False, "خطا در ارسال پیامک"
                
        except requests.exceptions.Timeout:
            logger.error("SMS API timeout")
            return False, "زمان ارسال پیامک به پایان رسید"
        except requests.exceptions.RequestException as e:
            logger.error(f"SMS API request failed: {str(e)}")
            return False, "خطا در اتصال به سرویس پیامک"
        except Exception as e:
            logger.error(f"Unexpected SMS error: {str(e)}")
            return False, "خطای غیرمنتظره در ارسال پیامک"

    def send_verification_sms(self, phone: str, name: str = '') -> Tuple[bool, str]:
        """Send verification SMS for successful actions"""
        try:
            phone = phone.replace('+98', '').replace(' ', '')
            if not phone.startswith('09'):
                phone = '0' + phone
                
            greeting = f"سلام {name}" if name else "سلام"
            message = f"{greeting}\nحساب کاربری شما در پلتفرم مال با موفقیت فعال شد.\nمال - فروشگاه‌ساز آنلاین"
            
            if settings.DEBUG:
                return self._send_mock_sms(phone, message)
            
            return self._send_real_sms(phone, message)
            
        except Exception as e:
            logger.error(f"Verification SMS failed: {str(e)}")
            return False, "خطا در ارسال پیامک تایید"

    def send_welcome_sms(self, phone: str, name: str, store_name: str = '') -> Tuple[bool, str]:
        """Send welcome SMS for new store owners"""
        try:
            phone = phone.replace('+98', '').replace(' ', '')
            if not phone.startswith('09'):
                phone = '0' + phone
                
            if store_name:
                message = f"سلام {name}\nفروشگاه {store_name} شما در پلتفرم مال آماده است!\nلینک فروشگاه: {store_name}.mall.ir\nمال - فروشگاه‌ساز آنلاین"
            else:
                message = f"سلام {name}\nخوش آمدید به پلتفرم مال!\nاکنون می‌توانید فروشگاه آنلاین خود را ایجاد کنید.\nمال - فروشگاه‌ساز آنلاین"
            
            if settings.DEBUG:
                return self._send_mock_sms(phone, message)
            
            return self._send_real_sms(phone, message)
            
        except Exception as e:
            logger.error(f"Welcome SMS failed: {str(e)}")
            return False, "خطا در ارسال پیامک خوش‌آمدگویی"


# Singleton instance
sms_service = SMSService()


def send_otp_sms(phone: str, otp_code: str, purpose: str = 'login') -> Tuple[bool, str]:
    """Convenience function to send OTP SMS"""
    return sms_service.send_otp(phone, otp_code, purpose)


def send_verification_sms(phone: str, name: str = '') -> Tuple[bool, str]:
    """Convenience function to send verification SMS"""
    return sms_service.send_verification_sms(phone, name)


def send_welcome_sms(phone: str, name: str, store_name: str = '') -> Tuple[bool, str]:
    """Convenience function to send welcome SMS"""
    return sms_service.send_welcome_sms(phone, name, store_name)
