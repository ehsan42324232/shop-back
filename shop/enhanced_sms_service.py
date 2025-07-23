# shop/enhanced_sms_service.py
import requests
import json
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.template import Template, Context
from .sms_models import SMSCampaign, SMSMessage, SMSTemplate, SMSProvider

logger = logging.getLogger('sms')


class SMSProviderFactory:
    """Factory for creating SMS provider instances"""
    
    @staticmethod
    def create_provider(provider_name):
        """Create appropriate SMS provider instance"""
        providers = {
            'kavenegar': KavenegarProvider,
            'ghasedak': GhasedakProvider,
            'farapayamak': FarapayamakProvider,
            'melipayamak': MelipayamakProvider,
            'ippanel': IPPanelProvider,
            'smsir': SMSIRProvider,
        }
        
        provider_class = providers.get(provider_name)
        if not provider_class:
            raise ValueError(f"SMS Provider {provider_name} not supported")
        
        return provider_class()


class BaseSMSProvider:
    """Base class for SMS providers"""
    
    def __init__(self):
        self.timeout = 30
        self.max_retries = 3
    
    def send_sms(self, phone, message, sender=None):
        """Send single SMS"""
        raise NotImplementedError
    
    def send_bulk_sms(self, recipients, message, sender=None):
        """Send bulk SMS"""
        raise NotImplementedError
    
    def get_delivery_status(self, message_id):
        """Get delivery status"""
        raise NotImplementedError
    
    def get_account_balance(self):
        """Get account balance"""
        raise NotImplementedError
    
    def normalize_phone(self, phone):
        """Normalize Iranian phone number"""
        # Remove all non-digit characters
        phone = ''.join(filter(str.isdigit, phone))
        
        # Handle different formats
        if phone.startswith('0098'):
            phone = phone[4:]
        elif phone.startswith('98'):
            phone = phone[2:]
        elif phone.startswith('0'):
            phone = phone[1:]
        
        # Add Iran country code
        if not phone.startswith('98'):
            phone = '98' + phone
        
        return phone
    
    def validate_iranian_mobile(self, phone):
        """Validate Iranian mobile number"""
        normalized = self.normalize_phone(phone)
        
        # Check length (should be 12 digits: 98 + 10 digits)
        if len(normalized) != 12:
            return False
        
        # Check Iranian mobile prefixes
        iranian_prefixes = [
            '9890', '9891', '9892', '9893', '9894', '9895', '9896', '9897', '9898', '9899',  # Irancell
            '9901', '9902', '9903', '9905', '9930', '9933', '9934', '9935', '9936', '9937', '9938', '9939',  # Hamrah-e Avval
            '9920', '9921', '9922',  # Rightel
            '9932',  # TeleKish
        ]
        
        return any(normalized.startswith(prefix) for prefix in iranian_prefixes)


class KavenegarProvider(BaseSMSProvider):
    """Kavenegar SMS Provider"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://api.kavenegar.com/v1"
        self.api_key = getattr(settings, 'KAVENEGAR_API_KEY', '')
    
    def send_sms(self, phone, message, sender=None):
        """Send SMS via Kavenegar"""
        try:
            phone = self.normalize_phone(phone)
            
            if not self.validate_iranian_mobile(phone):
                return {
                    'success': False,
                    'message': 'شماره موبایل معتبر نیست',
                    'error_code': 'INVALID_PHONE'
                }
            
            url = f"{self.base_url}/{self.api_key}/sms/send.json"
            
            data = {
                'receptor': phone,
                'message': message,
                'sender': sender or getattr(settings, 'SMS_DEFAULT_SENDER', '10008663')
            }
            
            response = requests.post(url, data=data, timeout=self.timeout)
            response_data = response.json()
            
            if response_data.get('return', {}).get('status') == 200:
                message_id = response_data['entries'][0]['messageid']
                return {
                    'success': True,
                    'message_id': str(message_id),
                    'message': 'پیامک با موفقیت ارسال شد',
                    'cost': response_data['entries'][0].get('cost', 0)
                }
            else:
                error_message = self._get_kavenegar_error(response_data.get('return', {}).get('message', ''))
                return {
                    'success': False,
                    'message': error_message,
                    'error_code': response_data.get('return', {}).get('status'),
                    'response': response_data
                }
                
        except requests.RequestException as e:
            logger.error(f"Kavenegar SMS error: {e}")
            return {
                'success': False,
                'message': f'خطا در ارسال پیامک: {str(e)}',
                'error_code': 'CONNECTION_ERROR'
            }
        except Exception as e:
            logger.error(f"Kavenegar unexpected error: {e}")
            return {
                'success': False,
                'message': f'خطای غیرمنتظره: {str(e)}',
                'error_code': 'UNEXPECTED_ERROR'
            }
    
    def send_bulk_sms(self, recipients, message, sender=None):
        """Send bulk SMS via Kavenegar"""
        try:
            # Normalize and validate all phone numbers
            valid_recipients = []
            invalid_phones = []
            
            for phone in recipients:
                normalized = self.normalize_phone(phone)
                if self.validate_iranian_mobile(normalized):
                    valid_recipients.append(normalized)
                else:
                    invalid_phones.append(phone)
            
            if not valid_recipients:
                return {
                    'success': False,
                    'message': 'هیچ شماره معتبری یافت نشد',
                    'invalid_phones': invalid_phones
                }
            
            url = f"{self.base_url}/{self.api_key}/sms/sendarray.json"
            
            data = {
                'receptor': valid_recipients,
                'message': [message] * len(valid_recipients),
                'sender': sender or getattr(settings, 'SMS_DEFAULT_SENDER', '10008663')
            }
            
            response = requests.post(url, json=data, timeout=self.timeout)
            response_data = response.json()
            
            if response_data.get('return', {}).get('status') == 200:
                results = []
                total_cost = 0
                
                for entry in response_data['entries']:
                    results.append({
                        'phone': entry['receptor'],
                        'message_id': str(entry['messageid']),
                        'status': entry['status'],
                        'cost': entry.get('cost', 0)
                    })
                    total_cost += entry.get('cost', 0)
                
                return {
                    'success': True,
                    'message': f'پیامک به {len(valid_recipients)} شماره ارسال شد',
                    'results': results,
                    'total_cost': total_cost,
                    'sent_count': len(valid_recipients),
                    'invalid_phones': invalid_phones
                }
            else:
                error_message = self._get_kavenegar_error(response_data.get('return', {}).get('message', ''))
                return {
                    'success': False,
                    'message': error_message,
                    'error_code': response_data.get('return', {}).get('status'),
                    'response': response_data
                }
                
        except Exception as e:
            logger.error(f"Kavenegar bulk SMS error: {e}")
            return {
                'success': False,
                'message': f'خطا در ارسال انبوه پیامک: {str(e)}',
                'error_code': 'BULK_SEND_ERROR'
            }
    
    def get_delivery_status(self, message_id):
        """Get delivery status from Kavenegar"""
        try:
            url = f"{self.base_url}/{self.api_key}/sms/status.json"
            
            data = {'messageid': message_id}
            
            response = requests.post(url, data=data, timeout=self.timeout)
            response_data = response.json()
            
            if response_data.get('return', {}).get('status') == 200:
                entry = response_data['entries'][0]
                status_map = {
                    1: 'در صف ارسال',
                    2: 'ارسال شده به مخابرات',
                    4: 'تحویل داده شده',
                    5: 'تحویل داده نشده',
                    8: 'رسیده به گوشی',
                    16: 'نرسیده به گوشی'
                }
                
                return {
                    'success': True,
                    'status': status_map.get(entry['status'], 'نامشخص'),
                    'status_code': entry['status'],
                    'message_id': str(entry['messageid'])
                }
            else:
                return {
                    'success': False,
                    'message': 'خطا در دریافت وضعیت',
                    'response': response_data
                }
                
        except Exception as e:
            logger.error(f"Kavenegar status check error: {e}")
            return {
                'success': False,
                'message': f'خطا در بررسی وضعیت: {str(e)}'
            }
    
    def get_account_balance(self):
        """Get account balance from Kavenegar"""
        try:
            url = f"{self.base_url}/{self.api_key}/account/info.json"
            
            response = requests.post(url, timeout=self.timeout)
            response_data = response.json()
            
            if response_data.get('return', {}).get('status') == 200:
                entry = response_data['entries']
                return {
                    'success': True,
                    'balance': entry['remaincredit'],
                    'expiry_date': entry['expiredate']
                }
            else:
                return {
                    'success': False,
                    'message': 'خطا در دریافت موجودی حساب'
                }
                
        except Exception as e:
            logger.error(f"Kavenegar balance check error: {e}")
            return {
                'success': False,
                'message': f'خطا در بررسی موجودی: {str(e)}'
            }
    
    def _get_kavenegar_error(self, error_message):
        """Get Persian error message for Kavenegar"""
        error_messages = {
            'رقم اعتبار کافی نمی‌باشد': 'موجودی حساب کافی نیست',
            'کلید API صحیح نمی‌باشد': 'کلید API معتبر نیست',
            'مقدار پارامتر message صحیح نمی‌باشد': 'متن پیام معتبر نیست',
            'مقدار پارامتر receptor صحیح نمی‌باشد': 'شماره گیرنده معتبر نیست',
            'سامانه در حال به‌روزرسانی می‌باشد': 'سرویس موقتاً در دسترس نیست',
        }
        return error_messages.get(error_message, error_message)


class GhasedakProvider(BaseSMSProvider):
    """Ghasedak SMS Provider"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://api.ghasedak.me/v2"
        self.api_key = getattr(settings, 'GHASEDAK_API_KEY', '')
    
    def send_sms(self, phone, message, sender=None):
        """Send SMS via Ghasedak"""
        try:
            phone = self.normalize_phone(phone)
            
            if not self.validate_iranian_mobile(phone):
                return {
                    'success': False,
                    'message': 'شماره موبایل معتبر نیست',
                    'error_code': 'INVALID_PHONE'
                }
            
            url = f"{self.base_url}/sms/send/simple"
            
            headers = {
                'apikey': self.api_key,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            data = {
                'receptor': phone,
                'message': message,
                'linenumber': sender or getattr(settings, 'SMS_DEFAULT_SENDER', '')
            }
            
            response = requests.post(url, headers=headers, data=data, timeout=self.timeout)
            response_data = response.json()
            
            if response_data.get('result', {}).get('code') == 200:
                items = response_data['result']['items']
                if items:
                    return {
                        'success': True,
                        'message_id': str(items[0]['messageid']),
                        'message': 'پیامک با موفقیت ارسال شد',
                        'cost': items[0].get('cost', 0)
                    }
            
            error_message = response_data.get('result', {}).get('message', 'خطا در ارسال پیامک')
            return {
                'success': False,
                'message': error_message,
                'error_code': response_data.get('result', {}).get('code'),
                'response': response_data
            }
            
        except Exception as e:
            logger.error(f"Ghasedak SMS error: {e}")
            return {
                'success': False,
                'message': f'خطا در ارسال پیامک: {str(e)}',
                'error_code': 'CONNECTION_ERROR'
            }


class EnhancedSMSService:
    """Enhanced SMS Service with campaigns and templates"""
    
    def __init__(self):
        self.default_provider = getattr(settings, 'SMS_DEFAULT_PROVIDER', 'kavenegar')
    
    def send_single_sms(self, phone, message, provider_name=None, sender=None):
        """Send single SMS"""
        try:
            provider_name = provider_name or self.default_provider
            provider = SMSProviderFactory.create_provider(provider_name)
            
            # Create SMS message record
            sms_message = SMSMessage.objects.create(
                recipient_phone=phone,
                message_text=message,
                provider=provider_name,
                sender=sender,
                status='pending'
            )
            
            # Send SMS
            result = provider.send_sms(phone, message, sender)
            
            # Update message record
            sms_message.provider_message_id = result.get('message_id', '')
            sms_message.provider_response = result
            sms_message.cost = result.get('cost', 0)
            
            if result['success']:
                sms_message.status = 'sent'
                sms_message.sent_at = timezone.now()
            else:
                sms_message.status = 'failed'
                sms_message.failure_reason = result.get('message', '')
            
            sms_message.save()
            
            return result
            
        except Exception as e:
            logger.error(f"Single SMS send error: {e}")
            return {
                'success': False,
                'message': f'خطا در ارسال پیامک: {str(e)}'
            }
    
    def send_bulk_sms(self, recipients, message, provider_name=None, sender=None):
        """Send bulk SMS"""
        try:
            provider_name = provider_name or self.default_provider
            provider = SMSProviderFactory.create_provider(provider_name)
            
            # Send bulk SMS
            result = provider.send_bulk_sms(recipients, message, sender)
            
            # Create SMS message records
            if result['success']:
                for item in result.get('results', []):
                    SMSMessage.objects.create(
                        recipient_phone=item['phone'],
                        message_text=message,
                        provider=provider_name,
                        sender=sender,
                        status='sent',
                        provider_message_id=item['message_id'],
                        provider_response=item,
                        cost=item.get('cost', 0),
                        sent_at=timezone.now()
                    )
            
            return result
            
        except Exception as e:
            logger.error(f"Bulk SMS send error: {e}")
            return {
                'success': False,
                'message': f'خطا در ارسال انبوه پیامک: {str(e)}'
            }
    
    def send_template_sms(self, template_id, phone, context_data=None, provider_name=None):
        """Send SMS using template"""
        try:
            template = SMSTemplate.objects.get(id=template_id, is_active=True)
            
            # Render template with context
            message = self.render_template(template.content, context_data or {})
            
            # Send SMS
            result = self.send_single_sms(phone, message, provider_name, template.sender)
            
            if result['success']:
                # Update template usage statistics
                template.usage_count += 1
                template.last_used_at = timezone.now()
                template.save()
            
            return result
            
        except SMSTemplate.DoesNotExist:
            return {
                'success': False,
                'message': 'قالب پیامک یافت نشد'
            }
        except Exception as e:
            logger.error(f"Template SMS send error: {e}")
            return {
                'success': False,
                'message': f'خطا در ارسال پیامک با قالب: {str(e)}'
            }
    
    def create_campaign(self, name, message, recipients, schedule_time=None, template_id=None):
        """Create SMS campaign"""
        try:
            with transaction.atomic():
                campaign = SMSCampaign.objects.create(
                    name=name,
                    message=message,
                    recipients=recipients,
                    scheduled_at=schedule_time,
                    template_id=template_id,
                    total_recipients=len(recipients),
                    status='scheduled' if schedule_time else 'pending'
                )
                
                # If not scheduled, send immediately
                if not schedule_time:
                    self.execute_campaign(campaign.id)
                
                return {
                    'success': True,
                    'campaign_id': campaign.id,
                    'message': 'کمپین با موفقیت ایجاد شد'
                }
                
        except Exception as e:
            logger.error(f"Campaign creation error: {e}")
            return {
                'success': False,
                'message': f'خطا در ایجاد کمپین: {str(e)}'
            }
    
    def execute_campaign(self, campaign_id):
        """Execute SMS campaign"""
        try:
            campaign = SMSCampaign.objects.get(id=campaign_id)
            
            if campaign.status not in ['pending', 'scheduled']:
                return {
                    'success': False,
                    'message': 'وضعیت کمپین اجازه اجرا را نمی‌دهد'
                }
            
            # Update campaign status
            campaign.status = 'running'
            campaign.started_at = timezone.now()
            campaign.save()
            
            # Send bulk SMS
            message = campaign.message
            if campaign.template:
                # Use template if specified
                message = campaign.template.content
            
            result = self.send_bulk_sms(
                campaign.recipients,
                message,
                campaign.provider,
                campaign.sender
            )
            
            # Update campaign results
            campaign.sent_count = result.get('sent_count', 0)
            campaign.failed_count = len(campaign.recipients) - campaign.sent_count
            campaign.total_cost = result.get('total_cost', 0)
            campaign.provider_response = result
            
            if result['success']:
                campaign.status = 'completed'
                campaign.completed_at = timezone.now()
            else:
                campaign.status = 'failed'
                campaign.failure_reason = result.get('message', '')
            
            campaign.save()
            
            return result
            
        except SMSCampaign.DoesNotExist:
            return {
                'success': False,
                'message': 'کمپین یافت نشد'
            }
        except Exception as e:
            logger.error(f"Campaign execution error: {e}")
            return {
                'success': False,
                'message': f'خطا در اجرای کمپین: {str(e)}'
            }
    
    def get_delivery_status(self, message_id, provider_name=None):
        """Get SMS delivery status"""
        try:
            sms_message = SMSMessage.objects.get(id=message_id)
            provider_name = provider_name or sms_message.provider
            
            provider = SMSProviderFactory.create_provider(provider_name)
            result = provider.get_delivery_status(sms_message.provider_message_id)
            
            if result['success']:
                # Update message status
                sms_message.delivery_status = result.get('status', '')
                sms_message.delivery_checked_at = timezone.now()
                sms_message.save()
            
            return result
            
        except SMSMessage.DoesNotExist:
            return {
                'success': False,
                'message': 'پیامک یافت نشد'
            }
        except Exception as e:
            logger.error(f"Delivery status check error: {e}")
            return {
                'success': False,
                'message': f'خطا در بررسی وضعیت تحویل: {str(e)}'
            }
    
    def render_template(self, template_content, context_data):
        """Render SMS template with context data"""
        try:
            template = Template(template_content)
            context = Context(context_data)
            return template.render(context)
        except Exception as e:
            logger.error(f"Template rendering error: {e}")
            return template_content
    
    def get_provider_balance(self, provider_name=None):
        """Get SMS provider account balance"""
        try:
            provider_name = provider_name or self.default_provider
            provider = SMSProviderFactory.create_provider(provider_name)
            
            return provider.get_account_balance()
            
        except Exception as e:
            logger.error(f"Balance check error: {e}")
            return {
                'success': False,
                'message': f'خطا در بررسی موجودی: {str(e)}'
            }
    
    def schedule_campaign_execution(self):
        """Execute scheduled campaigns (to be called by cron job)"""
        try:
            now = timezone.now()
            scheduled_campaigns = SMSCampaign.objects.filter(
                status='scheduled',
                scheduled_at__lte=now
            )
            
            results = []
            for campaign in scheduled_campaigns:
                result = self.execute_campaign(campaign.id)
                results.append({
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'result': result
                })
            
            return {
                'success': True,
                'message': f'{len(results)} کمپین اجرا شد',
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Scheduled campaign execution error: {e}")
            return {
                'success': False,
                'message': f'خطا در اجرای کمپین‌های زمان‌بندی شده: {str(e)}'
            }


# Common SMS templates for the shop platform
def create_default_sms_templates():
    """Create default SMS templates for the shop platform"""
    templates = [
        {
            'name': 'کد تایید',
            'code': 'otp_verification',
            'content': 'کد تایید شما: {{ otp_code }}\nاین کد تا {{ expiry_minutes }} دقیقه معتبر است.\n{{ shop_name }}',
            'category': 'auth',
            'variables': ['otp_code', 'expiry_minutes', 'shop_name']
        },
        {
            'name': 'تایید سفارش',
            'code': 'order_confirmation',
            'content': 'سفارش شما با کد {{ order_id }} ثبت شد.\nمبلغ: {{ amount }} ریال\nوضعیت: در انتظار پرداخت\n{{ shop_name }}',
            'category': 'order',
            'variables': ['order_id', 'amount', 'shop_name']
        },
        {
            'name': 'تایید پرداخت',
            'code': 'payment_success',
            'content': 'پرداخت شما با موفقیت انجام شد.\nکد مرجع: {{ reference_id }}\nمبلغ: {{ amount }} ریال\n{{ shop_name }}',
            'category': 'payment',
            'variables': ['reference_id', 'amount', 'shop_name']
        },
        {
            'name': 'ارسال سفارش',
            'code': 'order_shipped',
            'content': 'سفارش {{ order_id }} ارسال شد.\nکد رهگیری: {{ tracking_code }}\nزمان تحویل: {{ delivery_time }}\n{{ shop_name }}',
            'category': 'shipping',
            'variables': ['order_id', 'tracking_code', 'delivery_time', 'shop_name']
        },
        {
            'name': 'تحویل سفارش',
            'code': 'order_delivered',
            'content': 'سفارش {{ order_id }} تحویل داده شد.\nاز خرید شما متشکریم.\n{{ shop_name }}',
            'category': 'delivery',
            'variables': ['order_id', 'shop_name']
        },
        {
            'name': 'کمبود موجودی',
            'code': 'low_stock_alert',
            'content': 'محصول {{ product_name }} تنها {{ stock_count }} عدد در انبار باقی مانده است.\nسفارش دهید: {{ product_url }}\n{{ shop_name }}',
            'category': 'marketing',
            'variables': ['product_name', 'stock_count', 'product_url', 'shop_name']
        },
        {
            'name': 'تخفیف ویژه',
            'code': 'special_discount',
            'content': 'تخفیف ویژه {{ discount_percent }}٪ برای شما!\nکد تخفیف: {{ discount_code }}\nتا {{ expiry_date }} معتبر است.\n{{ shop_name }}',
            'category': 'marketing',
            'variables': ['discount_percent', 'discount_code', 'expiry_date', 'shop_name']
        },
    ]
    
    created_templates = []
    for template_data in templates:
        template, created = SMSTemplate.objects.get_or_create(
            code=template_data['code'],
            defaults={
                'name': template_data['name'],
                'content': template_data['content'],
                'category': template_data['category'],
                'variables': template_data['variables'],
                'is_active': True
            }
        )
        if created:
            created_templates.append(template)
    
    return created_templates
