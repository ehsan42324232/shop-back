# Mall Platform OTP Service
import requests
import logging
from django.conf import settings
from datetime import datetime

logger = logging.getLogger(__name__)


class OTPService:
    """OTP SMS service for Mall platform"""
    
    def __init__(self):
        # Iranian SMS provider configurations
        self.sms_providers = {
            'kavenegar': {
                'api_key': getattr(settings, 'KAVENEGAR_API_KEY', ''),
                'sender': getattr(settings, 'KAVENEGAR_SENDER', '10008663'),
                'url': 'https://api.kavenegar.com/v1/{api_key}/sms/send.json'
            },
            'melipayamak': {
                'username': getattr(settings, 'MELIPAYAMAK_USERNAME', ''),
                'password': getattr(settings, 'MELIPAYAMAK_PASSWORD', ''),
                'from': getattr(settings, 'MELIPAYAMAK_FROM', '50004001'),
                'url': 'https://rest.payamak-panel.com/api/SendSMS/SendSMS'
            },
            'smsir': {
                'api_key': getattr(settings, 'SMSIR_API_KEY', ''),
                'secret_key': getattr(settings, 'SMSIR_SECRET_KEY', ''),
                'line_number': getattr(settings, 'SMSIR_LINE_NUMBER', '30007732'),
                'url': 'https://ws.sms.ir/'
            }
        }
        
        # Default provider
        self.default_provider = getattr(settings, 'DEFAULT_SMS_PROVIDER', 'kavenegar')
        
        # OTP message template
        self.otp_template = getattr(
            settings, 
            'OTP_MESSAGE_TEMPLATE', 
            'کد تایید مال: {code}\nاین کد تا ۵ دقیقه معتبر است.\nmall.ir'
        )
    
    def send_otp_sms(self, phone, code):
        """Send OTP SMS to phone number"""
        try:
            message = self.otp_template.format(code=code)
            
            # Try sending with default provider first
            if self._send_with_provider(self.default_provider, phone, message):
                logger.info(f"OTP sent successfully to {phone} via {self.default_provider}")
                return True
            
            # If default provider fails, try other providers
            for provider_name in self.sms_providers.keys():
                if provider_name != self.default_provider:
                    if self._send_with_provider(provider_name, phone, message):
                        logger.info(f"OTP sent successfully to {phone} via {provider_name}")
                        return True
            
            logger.error(f"Failed to send OTP to {phone} with all providers")
            return False
            
        except Exception as e:
            logger.error(f"Error sending OTP to {phone}: {str(e)}")
            return False
    
    def _send_with_provider(self, provider_name, phone, message):
        """Send SMS with specific provider"""
        if provider_name not in self.sms_providers:
            return False
        
        provider_config = self.sms_providers[provider_name]
        
        try:
            if provider_name == 'kavenegar':
                return self._send_kavenegar(provider_config, phone, message)
            elif provider_name == 'melipayamak':
                return self._send_melipayamak(provider_config, phone, message)
            elif provider_name == 'smsir':
                return self._send_smsir(provider_config, phone, message)
            else:
                return False
        except Exception as e:
            logger.error(f"Error with {provider_name} provider: {str(e)}")
            return False
    
    def _send_kavenegar(self, config, phone, message):
        """Send SMS via Kavenegar"""
        if not config['api_key']:
            return False
        
        url = config['url'].format(api_key=config['api_key'])
        
        params = {
            'receptor': phone,
            'sender': config['sender'],
            'message': message
        }
        
        response = requests.post(url, data=params, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('return', {}).get('status') == 200:
                return True
        
        logger.error(f"Kavenegar error: {response.text}")
        return False
    
    def _send_melipayamak(self, config, phone, message):
        """Send SMS via Melipayamak"""
        if not config['username'] or not config['password']:
            return False
        
        payload = {
            'username': config['username'],
            'password': config['password'],
            'to': phone,
            'from': config['from'],
            'text': message,
            'isflash': False
        }
        
        response = requests.post(config['url'], json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('RetStatus') == 1:
                return True
        
        logger.error(f"Melipayamak error: {response.text}")
        return False
    
    def _send_smsir(self, config, phone, message):
        """Send SMS via SMS.ir"""
        if not config['api_key'] or not config['secret_key']:
            return False
        
        # First get token
        token_url = config['url'] + 'api/Token'
        token_payload = {
            'UserApiKey': config['api_key'],
            'SecretKey': config['secret_key']
        }
        
        token_response = requests.post(token_url, json=token_payload, timeout=10)
        
        if token_response.status_code != 200:
            return False
        
        token_result = token_response.json()
        if not token_result.get('IsSuccessful'):
            return False
        
        token = token_result.get('TokenKey')
        
        # Send SMS
        sms_url = config['url'] + 'api/MessageSend'
        headers = {'x-sms-ir-secure-token': token}
        
        sms_payload = {
            'Messages': [message],
            'MobileNumbers': [phone],
            'LineNumber': config['line_number'],
            'SendDateTime': '',
            'CanContinueInCaseOfError': True
        }
        
        sms_response = requests.post(sms_url, json=sms_payload, headers=headers, timeout=10)
        
        if sms_response.status_code == 200:
            sms_result = sms_response.json()
            if sms_result.get('IsSuccessful'):
                return True
        
        logger.error(f"SMS.ir error: {sms_response.text}")
        return False
    
    def send_welcome_sms(self, phone, name):
        """Send welcome SMS to new users"""
        try:
            message = f"سلام {name}!\nبه پلتفرم مال خوش آمدید. شما می‌توانید فروشگاه آنلاین خود را ایجاد کنید.\nmall.ir"
            
            # Use default provider
            return self._send_with_provider(self.default_provider, phone, message)
            
        except Exception as e:
            logger.error(f"Error sending welcome SMS to {phone}: {str(e)}")
            return False
    
    def send_store_approval_sms(self, phone, store_name):
        """Send store approval notification SMS"""
        try:
            message = f"تبریک! فروشگاه '{store_name}' شما تایید شد و آماده دریافت سفارش است.\nmall.ir"
            
            return self._send_with_provider(self.default_provider, phone, message)
            
        except Exception as e:
            logger.error(f"Error sending store approval SMS to {phone}: {str(e)}")
            return False
    
    def send_order_notification_sms(self, phone, order_id, store_name):
        """Send new order notification SMS to store owner"""
        try:
            message = f"سفارش جدید!\nسفارش #{order_id} برای فروشگاه '{store_name}' ثبت شد.\nبرای مشاهده وارد پنل شوید.\nmall.ir"
            
            return self._send_with_provider(self.default_provider, phone, message)
            
        except Exception as e:
            logger.error(f"Error sending order notification SMS to {phone}: {str(e)}")
            return False
    
    def send_order_status_sms(self, phone, order_id, status):
        """Send order status update SMS to customer"""
        try:
            status_messages = {
                'confirmed': 'تایید شد',
                'processing': 'در حال آماده‌سازی',
                'shipped': 'ارسال شد',
                'delivered': 'تحویل داده شد',
                'cancelled': 'لغو شد'
            }
            
            status_text = status_messages.get(status, status)
            message = f"وضعیت سفارش #{order_id} شما {status_text}.\nبرای جزئیات بیشتر به پنل کاربری مراجعه کنید.\nmall.ir"
            
            return self._send_with_provider(self.default_provider, phone, message)
            
        except Exception as e:
            logger.error(f"Error sending order status SMS to {phone}: {str(e)}")
            return False
    
    def send_promotional_sms(self, phone, message):
        """Send promotional SMS (be careful with spam regulations)"""
        try:
            # Add unsubscribe option
            full_message = f"{message}\n\nبرای لغو پیامک: STOP\nmall.ir"
            
            return self._send_with_provider(self.default_provider, phone, full_message)
            
        except Exception as e:
            logger.error(f"Error sending promotional SMS to {phone}: {str(e)}")
            return False
    
    def send_password_reset_sms(self, phone, reset_code):
        """Send password reset code SMS"""
        try:
            message = f"کد بازیابی رمز عبور مال: {reset_code}\nاین کد تا ۱۰ دقیقه معتبر است.\nmall.ir"
            
            return self._send_with_provider(self.default_provider, phone, message)
            
        except Exception as e:
            logger.error(f"Error sending password reset SMS to {phone}: {str(e)}")
            return False
    
    def send_verification_sms(self, phone, verification_code):
        """Send phone verification code SMS"""
        try:
            message = f"کد تایید شماره تلفن مال: {verification_code}\nاین کد تا ۵ دقیقه معتبر است.\nmall.ir"
            
            return self._send_with_provider(self.default_provider, phone, message)
            
        except Exception as e:
            logger.error(f"Error sending verification SMS to {phone}: {str(e)}")
            return False
    
    def send_payment_confirmation_sms(self, phone, order_id, amount):
        """Send payment confirmation SMS"""
        try:
            message = f"پرداخت موفق!\nسفارش #{order_id} - مبلغ: {amount:,} تومان\nبا تشکر از خرید شما.\nmall.ir"
            
            return self._send_with_provider(self.default_provider, phone, message)
            
        except Exception as e:
            logger.error(f"Error sending payment confirmation SMS to {phone}: {str(e)}")
            return False
    
    def get_provider_status(self):
        """Get status of all SMS providers"""
        status = {}
        
        for provider_name, config in self.sms_providers.items():
            try:
                if provider_name == 'kavenegar':
                    has_config = bool(config['api_key'])
                elif provider_name == 'melipayamak':
                    has_config = bool(config['username'] and config['password'])
                elif provider_name == 'smsir':
                    has_config = bool(config['api_key'] and config['secret_key'])
                else:
                    has_config = False
                
                status[provider_name] = {
                    'configured': has_config,
                    'is_default': provider_name == self.default_provider
                }
                
            except Exception as e:
                status[provider_name] = {
                    'configured': False,
                    'error': str(e),
                    'is_default': provider_name == self.default_provider
                }
        
        return status
    
    def test_sms_provider(self, provider_name, test_phone):
        """Test specific SMS provider"""
        if provider_name not in self.sms_providers:
            return False, "Provider not found"
        
        try:
            test_message = f"تست ارسال پیامک - {datetime.now().strftime('%H:%M:%S')}\nmall.ir"
            
            if self._send_with_provider(provider_name, test_phone, test_message):
                return True, "Test SMS sent successfully"
            else:
                return False, "Failed to send test SMS"
                
        except Exception as e:
            return False, f"Error: {str(e)}"


# Global OTP service instance
otp_service = OTPService()
