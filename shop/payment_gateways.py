# shop/payment_gateways.py
"""
Mall Platform - Iranian Payment Gateway Integration
Comprehensive payment integration for Iranian market
"""
import hashlib
import requests
import json
import logging
from datetime import datetime
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class PaymentGatewayBase:
    """Base class for payment gateways"""
    
    def __init__(self, merchant_id: str, sandbox: bool = True):
        self.merchant_id = merchant_id
        self.sandbox = sandbox
        
    def create_payment(self, amount: int, order_id: str, callback_url: str, **kwargs) -> Dict[str, Any]:
        """Create payment request"""
        raise NotImplementedError
        
    def verify_payment(self, authority: str, amount: int) -> Dict[str, Any]:
        """Verify payment"""
        raise NotImplementedError
        
    def check_status(self, authority: str) -> Dict[str, Any]:
        """Check payment status"""
        raise NotImplementedError


class ZarinpalGateway(PaymentGatewayBase):
    """ZarinPal payment gateway implementation"""
    
    def __init__(self, merchant_id: str, sandbox: bool = True):
        super().__init__(merchant_id, sandbox)
        self.base_url = "https://sandbox.zarinpal.com/pg/rest/WebGate/" if sandbox else "https://api.zarinpal.com/pg/rest/WebGate/"
        self.payment_url = "https://sandbox.zarinpal.com/pg/StartPay/" if sandbox else "https://www.zarinpal.com/pg/StartPay/"
        
    def create_payment(self, amount: int, order_id: str, callback_url: str, **kwargs) -> Dict[str, Any]:
        """Create ZarinPal payment request"""
        try:
            data = {
                "MerchantID": self.merchant_id,
                "Amount": amount,
                "Description": kwargs.get('description', f'پرداخت سفارش {order_id}'),
                "CallbackURL": callback_url,
                "Mobile": kwargs.get('mobile', ''),
                "Email": kwargs.get('email', '')
            }
            
            response = requests.post(
                f"{self.base_url}PaymentRequest.json",
                json=data,
                timeout=30
            )
            
            result = response.json()
            
            if result.get('Status') == 100:
                return {
                    'success': True,
                    'authority': result['Authority'],
                    'payment_url': f"{self.payment_url}{result['Authority']}",
                    'message': 'درخواست پرداخت با موفقیت ایجاد شد'
                }
            else:
                return {
                    'success': False,
                    'error_code': result.get('Status'),
                    'message': self._get_zarinpal_error_message(result.get('Status'))
                }
                
        except requests.RequestException as e:
            logger.error(f"ZarinPal payment request error: {e}")
            return {
                'success': False,
                'message': 'خطا در برقراری ارتباط با درگاه پرداخت'
            }
            
    def verify_payment(self, authority: str, amount: int) -> Dict[str, Any]:
        """Verify ZarinPal payment"""
        try:
            data = {
                "MerchantID": self.merchant_id,
                "Amount": amount,
                "Authority": authority
            }
            
            response = requests.post(
                f"{self.base_url}PaymentVerification.json",
                json=data,
                timeout=30
            )
            
            result = response.json()
            
            if result.get('Status') == 100 or result.get('Status') == 101:
                return {
                    'success': True,
                    'ref_id': result.get('RefID'),
                    'verified': True,
                    'message': 'پرداخت با موفقیت انجام شد'
                }
            else:
                return {
                    'success': False,
                    'error_code': result.get('Status'),
                    'verified': False,
                    'message': self._get_zarinpal_error_message(result.get('Status'))
                }
                
        except requests.RequestException as e:
            logger.error(f"ZarinPal verification error: {e}")
            return {
                'success': False,
                'verified': False,
                'message': 'خطا در تایید پرداخت'
            }
            
    def _get_zarinpal_error_message(self, status_code: int) -> str:
        """Get Persian error message for ZarinPal status codes"""
        error_messages = {
            -1: "اطلاعات ارسال شده ناقص است",
            -2: "IP یا مرچنت کد پذیرنده صحیح نیست",
            -3: "با توجه به محدودیت‌های شاپرک امکان پردازش وجود ندارد",
            -4: "سطح تایید پذیرنده پایین‌تر از سطح نقره‌ای است",
            -11: "درخواست مورد نظر یافت نشد",
            -12: "امکان ویرایش درخواست میسر نمی‌باشد",
            -21: "هیچ نوع عملیات مالی برای این تراکنش یافت نشد",
            -22: "تراکنش ناموفق می‌باشد",
            -33: "رقم تراکنش با رقم پرداخت شده مطابقت ندارد",
            -34: "سقف تقسیم تراکنش از لحاظ تعداد یا رقم عبور نموده است",
            -40: "اجازه دسترسی به متد مربوطه وجود ندارد",
            -41: "اطلاعات ارسال شده مربوط به AdditionalData غیرمعتبر می‌باشد",
            -42: "مدت زمان معتبر طول عمر شناسه پرداخت بایستی بین 30 دقیقه تا 45 روز می‌باشد",
            -54: "درخواست مورد نظر آرشیو شده است"
        }
        return error_messages.get(status_code, "خطای ناشناخته در پردازش پرداخت")


class MellatGateway(PaymentGatewayBase):
    """Bank Mellat (Behpardakht) payment gateway"""
    
    def __init__(self, merchant_id: str, username: str, password: str, sandbox: bool = True):
        super().__init__(merchant_id, sandbox)
        self.username = username
        self.password = password
        self.base_url = "https://bpm.shaparak.ir/pgwchannel/services/" if not sandbox else "https://sandbox.shaparak.ir/pgwchannel/services/"
        
    def create_payment(self, amount: int, order_id: str, callback_url: str, **kwargs) -> Dict[str, Any]:
        """Create Mellat payment request"""
        try:
            # Convert amount to Rials (Mellat expects Rials)
            amount_rials = amount * 10
            
            data = {
                'terminalId': self.merchant_id,
                'userName': self.username,
                'userPassword': self.password,
                'orderId': order_id,
                'amount': amount_rials,
                'localDate': datetime.now().strftime('%Y%m%d'),
                'localTime': datetime.now().strftime('%H%M%S'),
                'additionalData': kwargs.get('description', ''),
                'callBackUrl': callback_url,
                'payerId': kwargs.get('payer_id', '0')
            }
            
            # Create SOAP request for Mellat
            soap_body = self._create_soap_request('bpPayRequest', data)
            
            response = requests.post(
                f"{self.base_url}PaymentGateway.asmx",
                data=soap_body,
                headers={'Content-Type': 'text/xml; charset=utf-8'},
                timeout=30
            )
            
            # Parse SOAP response
            result = self._parse_soap_response(response.text)
            
            if result and result.split(',')[0] == '0':
                ref_id = result.split(',')[1]
                return {
                    'success': True,
                    'ref_id': ref_id,
                    'payment_url': f"https://bpm.shaparak.ir/pgwchannel/startpay.mellat?RefId={ref_id}",
                    'message': 'درخواست پرداخت با موفقیت ایجاد شد'
                }
            else:
                return {
                    'success': False,
                    'error_code': result.split(',')[0] if result else 'unknown',
                    'message': self._get_mellat_error_message(result.split(',')[0] if result else '')
                }
                
        except Exception as e:
            logger.error(f"Mellat payment request error: {e}")
            return {
                'success': False,
                'message': 'خطا در برقراری ارتباط با درگاه پرداخت'
            }
            
    def verify_payment(self, ref_id: str, sale_order_id: str, sale_reference_id: str) -> Dict[str, Any]:
        """Verify Mellat payment"""
        try:
            # First settle the transaction
            settle_data = {
                'terminalId': self.merchant_id,
                'userName': self.username,
                'userPassword': self.password,
                'orderId': sale_order_id,
                'saleOrderId': sale_order_id,
                'saleReferenceId': sale_reference_id
            }
            
            soap_body = self._create_soap_request('bpSettleRequest', settle_data)
            
            response = requests.post(
                f"{self.base_url}PaymentGateway.asmx",
                data=soap_body,
                headers={'Content-Type': 'text/xml; charset=utf-8'},
                timeout=30
            )
            
            result = self._parse_soap_response(response.text)
            
            if result == '0':
                return {
                    'success': True,
                    'verified': True,
                    'ref_id': sale_reference_id,
                    'message': 'پرداخت با موفقیت تایید شد'
                }
            else:
                return {
                    'success': False,
                    'verified': False,
                    'error_code': result,
                    'message': self._get_mellat_error_message(result)
                }
                
        except Exception as e:
            logger.error(f"Mellat verification error: {e}")
            return {
                'success': False,
                'verified': False,
                'message': 'خطا در تایید پرداخت'
            }
            
    def _create_soap_request(self, method: str, data: Dict) -> str:
        """Create SOAP request for Mellat"""
        params = ''.join([f'<{key}>{value}</{key}>' for key, value in data.items()])
        
        return f"""<?xml version="1.0" encoding="utf-8"?>
        <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
                       xmlns:xsd="http://www.w3.org/2001/XMLSchema" 
                       xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <{method} xmlns="http://interfaces.core.sw.bps.com/">
              {params}
            </{method}>
          </soap:Body>
        </soap:Envelope>"""
        
    def _parse_soap_response(self, response_text: str) -> str:
        """Parse SOAP response from Mellat"""
        try:
            # Simple XML parsing for response
            start_tag = '<return>'
            end_tag = '</return>'
            start_idx = response_text.find(start_tag)
            end_idx = response_text.find(end_tag)
            
            if start_idx != -1 and end_idx != -1:
                return response_text[start_idx + len(start_tag):end_idx]
            return ""
        except Exception:
            return ""
            
    def _get_mellat_error_message(self, error_code: str) -> str:
        """Get Persian error message for Mellat error codes"""
        error_messages = {
            '11': 'شماره کارت نامعتبر است',
            '12': 'موجودی کافی نیست',
            '13': 'رمز نادرست است',
            '14': 'تعداد دفعات وارد کردن رمز بیش از حد مجاز است',
            '15': 'کارت نامعتبر است',
            '16': 'دفعات برداشت وجه بیش از حد مجاز است',
            '17': 'کاربر از انجام تراکنش منصرف شده است',
            '18': 'تاریخ انقضای کارت گذشته است',
            '19': 'مبلغ برداشت وجه بیش از حد مجاز است',
            '111': 'صادر کننده کارت نامعتبر است',
            '112': 'خطای سوییچ صادر کننده کارت',
            '113': 'پاسخی از صادر کننده کارت دریافت نشد',
            '114': 'دارنده کارت مجاز به انجام این تراکنش نیست'
        }
        return error_messages.get(error_code, f'خطای ناشناخته: {error_code}')


class SamanGateway(PaymentGatewayBase):
    """Saman Bank payment gateway"""
    
    def __init__(self, merchant_id: str, sandbox: bool = True):
        super().__init__(merchant_id, sandbox)
        self.base_url = "https://sep.shaparak.ir/payments/" if not sandbox else "https://sandbox.sep.shaparak.ir/payments/"
        
    def create_payment(self, amount: int, order_id: str, callback_url: str, **kwargs) -> Dict[str, Any]:
        """Create Saman payment request"""
        try:
            data = {
                'TerminalId': self.merchant_id,
                'Amount': amount,
                'OrderId': order_id,
                'CallbackUrl': callback_url,
                'Description': kwargs.get('description', f'پرداخت سفارش {order_id}'),
                'Mobile': kwargs.get('mobile', ''),
                'Email': kwargs.get('email', '')
            }
            
            response = requests.post(
                f"{self.base_url}initpayment.asmx/RequestToken",
                json=data,
                timeout=30
            )
            
            result = response.json()
            
            if result.get('Status') == 1:
                token = result.get('Token')
                return {
                    'success': True,
                    'token': token,
                    'payment_url': f"{self.base_url}payment.aspx?Token={token}",
                    'message': 'درخواست پرداخت با موفقیت ایجاد شد'
                }
            else:
                return {
                    'success': False,
                    'error_code': result.get('Status'),
                    'message': self._get_saman_error_message(result.get('Status'))
                }
                
        except Exception as e:
            logger.error(f"Saman payment request error: {e}")
            return {
                'success': False,
                'message': 'خطا در برقراری ارتباط با درگاه پرداخت'
            }
            
    def verify_payment(self, ref_num: str, order_id: str) -> Dict[str, Any]:
        """Verify Saman payment"""
        try:
            data = {
                'TerminalNumber': self.merchant_id,
                'RefNum': ref_num
            }
            
            response = requests.post(
                f"{self.base_url}verify.asmx/VerifyTransaction",
                json=data,
                timeout=30
            )
            
            result = response.json()
            amount = result.get('Amount', 0)
            
            if amount > 0:
                return {
                    'success': True,
                    'verified': True,
                    'amount': amount,
                    'ref_num': ref_num,
                    'message': 'پرداخت با موفقیت تایید شد'
                }
            else:
                return {
                    'success': False,
                    'verified': False,
                    'error_code': amount,
                    'message': self._get_saman_error_message(amount)
                }
                
        except Exception as e:
            logger.error(f"Saman verification error: {e}")
            return {
                'success': False,
                'verified': False,
                'message': 'خطا در تایید پرداخت'
            }
            
    def _get_saman_error_message(self, error_code: int) -> str:
        """Get Persian error message for Saman error codes"""
        error_messages = {
            -1: 'خطا در پردازش',
            -3: 'ورودی‌ها حاوی کاراکترهای غیرمجاز می‌باشند',
            -4: 'کلمه عبور یا کد فروشنده اشتباه است',
            -6: 'تراکنش قبلاً برگشت داده شده است',
            -7: 'رسید دیجیتالی تهی است',
            -8: 'طول ورودی‌ها بیشتر از حد مجاز است',
            -9: 'وجود کاراکترهای غیرمجاز در مبلغ برگشتی',
            -10: 'رسید دیجیتالی حاوی کاراکترهای غیرمجاز است',
            -11: 'طول ورودی‌ها کمتر از حد مجاز است',
            -12: 'مبلغ برگشتی منفی است',
            -13: 'مبلغ برگشتی برای برگشت جزئی بیش از مبلغ برگشت نخورده ی تراکنش اصلی است',
            -14: 'چنین تراکنشی تعریف نشده است',
            -15: 'مبلغ برگشتی به صورت اعشاری داده شده است',
            -16: 'خطای داخلی سیستم',
            -17: 'برگشت زدن جزیی تراکنش مجاز نمی‌باشد',
            -18: 'IP فروشنده نا معتبر است'
        }
        return error_messages.get(error_code, f'خطای ناشناخته: {error_code}')


# Payment Gateway Factory
class PaymentGatewayFactory:
    """Factory class to create payment gateway instances"""
    
    @staticmethod
    def create_gateway(gateway_type: str, config: Dict[str, Any]) -> PaymentGatewayBase:
        """Create payment gateway instance based on type"""
        gateway_type = gateway_type.lower()
        
        if gateway_type == 'zarinpal':
            return ZarinpalGateway(
                merchant_id=config['merchant_id'],
                sandbox=config.get('sandbox', True)
            )
        elif gateway_type == 'mellat':
            return MellatGateway(
                merchant_id=config['merchant_id'],
                username=config['username'],
                password=config['password'],
                sandbox=config.get('sandbox', True)
            )
        elif gateway_type == 'saman':
            return SamanGateway(
                merchant_id=config['merchant_id'],
                sandbox=config.get('sandbox', True)
            )
        else:
            raise ValueError(f"Unsupported gateway type: {gateway_type}")


# Payment Service Manager
class PaymentServiceManager:
    """Centralized payment service manager"""
    
    def __init__(self):
        self.gateways = {}
        self._load_gateways()
        
    def _load_gateways(self):
        """Load configured payment gateways"""
        gateway_configs = getattr(settings, 'PAYMENT_GATEWAYS', {})
        
        for gateway_name, config in gateway_configs.items():
            if config.get('enabled', False):
                try:
                    self.gateways[gateway_name] = PaymentGatewayFactory.create_gateway(
                        config['type'], config
                    )
                except Exception as e:
                    logger.error(f"Failed to load gateway {gateway_name}: {e}")
                    
    def get_gateway(self, gateway_name: str) -> Optional[PaymentGatewayBase]:
        """Get payment gateway by name"""
        return self.gateways.get(gateway_name)
        
    def get_available_gateways(self) -> Dict[str, PaymentGatewayBase]:
        """Get all available payment gateways"""
        return self.gateways
        
    def create_payment(self, gateway_name: str, amount: int, order_id: str, 
                      callback_url: str, **kwargs) -> Dict[str, Any]:
        """Create payment using specified gateway"""
        gateway = self.get_gateway(gateway_name)
        if not gateway:
            return {
                'success': False,
                'message': f'درگاه پرداخت {gateway_name} در دسترس نیست'
            }
            
        return gateway.create_payment(amount, order_id, callback_url, **kwargs)
        
    def verify_payment(self, gateway_name: str, **kwargs) -> Dict[str, Any]:
        """Verify payment using specified gateway"""
        gateway = self.get_gateway(gateway_name)
        if not gateway:
            return {
                'success': False,
                'verified': False,
                'message': f'درگاه پرداخت {gateway_name} در دسترس نیست'
            }
            
        if gateway_name == 'zarinpal':
            return gateway.verify_payment(kwargs['authority'], kwargs['amount'])
        elif gateway_name == 'mellat':
            return gateway.verify_payment(
                kwargs['ref_id'], kwargs['sale_order_id'], kwargs['sale_reference_id']
            )
        elif gateway_name == 'saman':
            return gateway.verify_payment(kwargs['ref_num'], kwargs['order_id'])
        else:
            return {
                'success': False,
                'verified': False,
                'message': 'نوع درگاه پرداخت پشتیبانی نمی‌شود'
            }


# Global payment service instance
payment_service = PaymentServiceManager()
