import requests
import hashlib
import json
from datetime import datetime
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class IranianPaymentGateway:
    """Iranian payment gateway integration for Mall platform"""
    
    def __init__(self):
        self.zarinpal_merchant_id = getattr(settings, 'ZARINPAL_MERCHANT_ID', '')
        self.mellat_terminal_id = getattr(settings, 'MELLAT_TERMINAL_ID', '')
        self.mellat_username = getattr(settings, 'MELLAT_USERNAME', '')
        self.mellat_password = getattr(settings, 'MELLAT_PASSWORD', '')
        
    def zarinpal_request_payment(self, amount, description, email='', mobile=''):
        """Request payment through Zarinpal"""
        try:
            url = 'https://api.zarinpal.com/pg/v4/payment/request.json'
            
            data = {
                'merchant_id': self.zarinpal_merchant_id,
                'amount': int(amount),  # Amount in Rials
                'description': description,
                'callback_url': settings.SITE_URL + '/api/payment/zarinpal/callback/',
                'metadata': {
                    'email': email,
                    'mobile': mobile
                }
            }
            
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            
            if result.get('data', {}).get('code') == 100:
                authority = result['data']['authority']
                payment_url = f"https://www.zarinpal.com/pg/StartPay/{authority}"
                
                return {
                    'success': True,
                    'authority': authority,
                    'payment_url': payment_url,
                    'message': 'درخواست پرداخت با موفقیت ایجاد شد'
                }
            else:
                return {
                    'success': False,
                    'error': result.get('errors', 'خطا در ایجاد درخواست پرداخت')
                }
                
        except Exception as e:
            logger.error(f"Zarinpal payment request error: {str(e)}")
            return {
                'success': False,
                'error': 'خطا در ارتباط با درگاه پرداخت'
            }
    
    def zarinpal_verify_payment(self, authority, amount):
        """Verify Zarinpal payment"""
        try:
            url = 'https://api.zarinpal.com/pg/v4/payment/verify.json'
            
            data = {
                'merchant_id': self.zarinpal_merchant_id,
                'amount': int(amount),
                'authority': authority
            }
            
            response = requests.post(url, json=data, timeout=10)
            result = response.json()
            
            if result.get('data', {}).get('code') == 100:
                return {
                    'success': True,
                    'ref_id': result['data']['ref_id'],
                    'card_hash': result['data'].get('card_hash'),
                    'card_pan': result['data'].get('card_pan'),
                    'message': 'پرداخت با موفقیت تایید شد'
                }
            else:
                return {
                    'success': False,
                    'error': 'پرداخت تایید نشد'
                }
                
        except Exception as e:
            logger.error(f"Zarinpal payment verification error: {str(e)}")
            return {
                'success': False,
                'error': 'خطا در تایید پرداخت'
            }
    
    def mellat_request_payment(self, amount, order_id, callback_url):
        """Request payment through Mellat Bank"""
        try:
            # Mellat Bank SOAP service
            url = 'https://bpm.shaparak.ir/pgwchannel/services/pgw'
            
            # Generate payment request
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'http://interfaces.core.sw.bps.com/IPaymentRequest/PaymentRequest'
            }
            
            soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
            <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                           xmlns:int="http://interfaces.core.sw.bps.com/">
                <soap:Header/>
                <soap:Body>
                    <int:PaymentRequest>
                        <int:terminalId>{self.mellat_terminal_id}</int:terminalId>
                        <int:userName>{self.mellat_username}</int:userName>
                        <int:userPassword>{self.mellat_password}</int:userPassword>
                        <int:orderId>{order_id}</int:orderId>
                        <int:amount>{int(amount)}</int:amount>
                        <int:localDate>{datetime.now().strftime('%Y%m%d')}</int:localDate>
                        <int:localTime>{datetime.now().strftime('%H%M%S')}</int:localTime>
                        <int:additionalData></int:additionalData>
                        <int:callBackUrl>{callback_url}</int:callBackUrl>
                        <int:payerId>0</int:payerId>
                    </int:PaymentRequest>
                </soap:Body>
            </soap:Envelope>"""
            
            response = requests.post(url, data=soap_body, headers=headers, timeout=30)
            
            # Parse response
            if '0,' in response.text:
                parts = response.text.split(',')
                if len(parts) >= 2:
                    ref_id = parts[1]
                    payment_url = f"https://bpm.shaparak.ir/pgwchannel/startpay.mellat?RefId={ref_id}"
                    
                    return {
                        'success': True,
                        'ref_id': ref_id,
                        'payment_url': payment_url,
                        'message': 'درخواست پرداخت با موفقیت ایجاد شد'
                    }
            
            return {
                'success': False,
                'error': 'خطا در ایجاد درخواست پرداخت ملت'
            }
            
        except Exception as e:
            logger.error(f"Mellat payment request error: {str(e)}")
            return {
                'success': False,
                'error': 'خطا در ارتباط با درگاه ملت'
            }
    
    def mellat_verify_payment(self, sale_order_id, sale_reference_id):
        """Verify Mellat Bank payment"""
        try:
            url = 'https://bpm.shaparak.ir/pgwchannel/services/pgw'
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'http://interfaces.core.sw.bps.com/IPaymentVerification/PaymentVerification'
            }
            
            soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
            <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                           xmlns:int="http://interfaces.core.sw.bps.com/">
                <soap:Header/>
                <soap:Body>
                    <int:PaymentVerification>
                        <int:terminalId>{self.mellat_terminal_id}</int:terminalId>
                        <int:userName>{self.mellat_username}</int:userName>
                        <int:userPassword>{self.mellat_password}</int:userPassword>
                        <int:orderId>{sale_order_id}</int:orderId>
                        <int:saleOrderId>{sale_order_id}</int:saleOrderId>
                        <int:saleReferenceId>{sale_reference_id}</int:saleReferenceId>
                    </int:PaymentVerification>
                </soap:Body>
            </soap:Envelope>"""
            
            response = requests.post(url, data=soap_body, headers=headers, timeout=30)
            
            if '0' in response.text:
                return {
                    'success': True,
                    'message': 'پرداخت با موفقیت تایید شد'
                }
            else:
                return {
                    'success': False,
                    'error': 'پرداخت تایید نشد'
                }
                
        except Exception as e:
            logger.error(f"Mellat payment verification error: {str(e)}")
            return {
                'success': False,
                'error': 'خطا در تایید پرداخت'
            }

class PaymentService:
    """Main payment service for Mall platform"""
    
    def __init__(self):
        self.gateway = IranianPaymentGateway()
    
    def create_payment_request(self, order, gateway_type='zarinpal'):
        """Create payment request for an order"""
        try:
            amount = int(order.total_amount)
            description = f"پرداخت سفارش {order.order_number}"
            
            if gateway_type == 'zarinpal':
                result = self.gateway.zarinpal_request_payment(
                    amount=amount,
                    description=description,
                    email=order.customer_email,
                    mobile=order.customer_phone
                )
            elif gateway_type == 'mellat':
                callback_url = settings.SITE_URL + '/api/payment/mellat/callback/'
                result = self.gateway.mellat_request_payment(
                    amount=amount,
                    order_id=order.id,
                    callback_url=callback_url
                )
            else:
                return {
                    'success': False,
                    'error': 'درگاه پرداخت پشتیبانی نمی‌شود'
                }
            
            if result['success']:
                # Store payment info in cache
                cache_key = f"payment_{order.id}"
                cache.set(cache_key, {
                    'order_id': order.id,
                    'amount': amount,
                    'gateway': gateway_type,
                    'authority': result.get('authority'),
                    'ref_id': result.get('ref_id'),
                    'created_at': datetime.now().isoformat()
                }, timeout=1800)  # 30 minutes
            
            return result
            
        except Exception as e:
            logger.error(f"Payment request creation error: {str(e)}")
            return {
                'success': False,
                'error': 'خطا در ایجاد درخواست پرداخت'
            }
    
    def verify_payment(self, order_id, authority=None, ref_id=None, gateway_type='zarinpal'):
        """Verify payment for an order"""
        try:
            # Get payment info from cache
            cache_key = f"payment_{order_id}"
            payment_info = cache.get(cache_key)
            
            if not payment_info:
                return {
                    'success': False,
                    'error': 'اطلاعات پرداخت یافت نشد'
                }
            
            if gateway_type == 'zarinpal':
                result = self.gateway.zarinpal_verify_payment(
                    authority=authority or payment_info['authority'],
                    amount=payment_info['amount']
                )
            elif gateway_type == 'mellat':
                result = self.gateway.mellat_verify_payment(
                    sale_order_id=order_id,
                    sale_reference_id=ref_id
                )
            else:
                return {
                    'success': False,
                    'error': 'درگاه پرداخت پشتیبانی نمی‌شود'
                }
            
            # Clear cache if successful
            if result['success']:
                cache.delete(cache_key)
            
            return result
            
        except Exception as e:
            logger.error(f"Payment verification error: {str(e)}")
            return {
                'success': False,
                'error': 'خطا در تایید پرداخت'
            }
