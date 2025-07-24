# shop/live_sms_provider.py
"""
Mall Platform - Live SMS Provider Integration  
Real SMS service integration for Iranian providers
"""
import requests
import logging
from typing import Dict, Any, Optional
from django.conf import settings

logger = logging.getLogger(__name__)

class LiveSMSProvider:
    """Live SMS service provider for Iranian market"""
    
    def __init__(self, provider_name: str, api_key: str, username: str = '', password: str = '', sandbox: bool = True):
        self.provider_name = provider_name
        self.api_key = api_key
        self.username = username  
        self.password = password
        self.sandbox = sandbox
        
        # Provider configurations
        self.providers_config = {
            'kavenegar': {
                'url': 'https://api.kavenegar.com/v1/{}/sms/send.json',
                'sandbox_url': 'https://api.kavenegar.com/v1/{}/sms/send.json'
            },
            'sms_ir': {
                'url': 'https://ws.sms.ir/api/MessageSend',
                'sandbox_url': 'https://ws.sms.ir/api/MessageSend'
            },
            'farapayamak': {
                'url': 'https://rest.payamak-panel.com/api/SendSMS/SendSMS',
                'sandbox_url': 'https://rest.payamak-panel.com/api/SendSMS/SendSMS'
            }
        }
    
    def send_sms(self, phone_number: str, message: str, template_type: str = 'general') -> Dict[str, Any]:
        """Send SMS via configured provider"""
        try:
            if self.provider_name == 'kavenegar':
                return self._send_kavenegar(phone_number, message)
            elif self.provider_name == 'sms_ir':
                return self._send_sms_ir(phone_number, message)
            elif self.provider_name == 'farapayamak':
                return self._send_farapayamak(phone_number, message)
            else:
                return {
                    'success': False,
                    'message': 'ارائه‌دهنده SMS پشتیبانی نمی‌شود'
                }
                
        except Exception as e:
            logger.error(f"SMS send error with {self.provider_name}: {e}")
            return {
                'success': False,
                'message': 'خطا در ارسال پیامک'
            }
    
    def _send_kavenegar(self, phone_number: str, message: str) -> Dict[str, Any]:
        """Send SMS via Kavenegar"""
        url = self.providers_config['kavenegar']['url'].format(self.api_key)
        
        data = {
            'receptor': phone_number,
            'message': message,
            'sender': '10008663'  # Default Kavenegar sender
        }
        
        response = requests.post(url, data=data, timeout=30)
        result = response.json()
        
        if result.get('return', {}).get('status') == 200:
            entries = result.get('entries', [])
            if entries:
                return {
                    'success': True,
                    'message_id': str(entries[0].get('messageid')),
                    'cost': entries[0].get('cost', 0),
                    'status': entries[0].get('status'),
                    'message': 'پیامک با موفقیت ارسال شد'
                }
        
        return {
            'success': False,
            'message': result.get('return', {}).get('message', 'خطا در ارسال پیامک')
        }


# SMS Service Manager with live providers
class LiveSMSManager:
    """Live SMS service manager"""
    
    def __init__(self):
        self.providers = {}
        self._load_live_providers()
    
    def _load_live_providers(self):
        """Load live SMS providers from settings"""
        sms_config = getattr(settings, 'LIVE_SMS_PROVIDERS', {})
        
        for provider_name, config in sms_config.items():
            if config.get('enabled', False):
                try:
                    self.providers[provider_name] = LiveSMSProvider(
                        provider_name=provider_name,
                        api_key=config['api_key'],
                        username=config.get('username', ''),
                        password=config.get('password', ''),
                        sandbox=config.get('sandbox', True)
                    )
                except Exception as e:
                    logger.error(f"Failed to load SMS provider {provider_name}: {e}")
    
    def send_sms(self, phone_number: str, message: str, template_type: str = 'general', preferred_provider: str = None) -> Dict[str, Any]:
        """Send SMS with fallback providers"""
        providers_to_try = []
        
        # Use preferred provider first
        if preferred_provider and preferred_provider in self.providers:
            providers_to_try.append(preferred_provider)
        
        # Add other providers as fallback
        for provider_name in self.providers:
            if provider_name not in providers_to_try:
                providers_to_try.append(provider_name)
        
        last_error = None
        
        for provider_name in providers_to_try:
            try:
                provider = self.providers[provider_name]
                result = provider.send_sms(phone_number, message, template_type)
                
                if result['success']:
                    result['provider_used'] = provider_name
                    return result
                else:
                    last_error = result.get('message', 'خطای ناشناخته')
                    
            except Exception as e:
                logger.error(f"SMS provider {provider_name} failed: {e}")
                last_error = str(e)
        
        return {
            'success': False,
            'message': last_error or 'تمام ارائه‌دهندگان SMS در دسترس نیستند'
        }


# Global live SMS manager
live_sms_manager = LiveSMSManager()
