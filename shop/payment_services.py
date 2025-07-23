# shop/payment_services.py
import requests
import hashlib
import json
import uuid
from decimal import Decimal
from datetime import datetime, timedelta
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from .payment_models import Payment, PaymentGateway, PaymentAttempt
import logging

logger = logging.getLogger('payment')


class PaymentGatewayFactory:
    """Factory for creating payment gateway instances"""
    
    @staticmethod
    def create_gateway(gateway_name):
        """Create appropriate gateway instance"""
        gateways = {
            'zarinpal': ZarinpalGateway,
            'mellat': MellatGateway,
            'parsian': ParsianGateway,
            'saman': SamanGateway,
            'pasargad': PasargadGateway,
            'melli': MelliGateway,
            'saderat': SaderatGateway,
            'sep': SEPGateway,
        }
        
        gateway_class = gateways.get(gateway_name)
        if not gateway_class:
            raise ValueError(f"Gateway {gateway_name} not supported")
        
        return gateway_class()


class BasePaymentGateway:
    """Base class for payment gateways"""
    
    def __init__(self):
        self.gateway_model = None
        self.timeout = 30
    
    def prepare_payment(self, payment):
        """Prepare payment request"""
        raise NotImplementedError
    
    def verify_payment(self, payment, request_data):
        """Verify payment response"""
        raise NotImplementedError
    
    def create_refund(self, payment, amount, reason):
        """Create refund request"""
        raise NotImplementedError
    
    def get_payment_url(self, authority):
        """Get payment redirect URL"""
        raise NotImplementedError
    
    def log_attempt(self, payment, response, status_code, message):
        """Log payment attempt"""
        attempt_number = payment.attempts.count() + 1
        PaymentAttempt.objects.create(
            payment=payment,
            attempt_number=attempt_number,
            gateway_response=response,
            status_code=str(status_code),
            message=message
        )


class ZarinpalGateway(BasePaymentGateway):
    """Zarinpal Payment Gateway"""
    
    def __init__(self):
        super().__init__()
        self.sandbox_url = "https://sandbox.zarinpal.com/pg/rest/WebGate/"
        self.production_url = "https://api.zarinpal.com/pg/rest/WebGate/"
        self.payment_url = "https://www.zarinpal.com/pg/StartPay/"
        
    def get_base_url(self):
        """Get base URL based on environment"""
        if settings.DEBUG:
            return self.sandbox_url
        return self.production_url
    
    def prepare_payment(self, payment):
        """Prepare Zarinpal payment"""
        try:
            gateway = payment.gateway
            
            # Prepare request data
            request_data = {
                'merchant_id': gateway.merchant_id,
                'amount': payment.final_amount,
                'description': f"پرداخت سفارش #{payment.order.id}",
                'callback_url': self._get_callback_url(),
                'metadata': {
                    'mobile': payment.customer_phone,
                    'email': payment.customer_email or '',
                }
            }
            
            # Log request
            payment.request_log = request_data
            payment.save()
            
            # Send request
            response = requests.post(
                f"{self.get_base_url()}PaymentRequest.json",
                json=request_data,
                timeout=self.timeout
            )
            
            response_data = response.json()
            
            # Log response
            payment.response_log = response_data
            payment.save()
            
            # Log attempt
            self.log_attempt(payment, response_data, response.status_code, "Payment request")
            
            if response_data.get('data', {}).get('code') == 100:
                # Success
                authority = response_data['data']['authority']
                payment.gateway_authority = authority
                payment.status = 'processing'
                payment.save()
                
                return {
                    'success': True,
                    'authority': authority,
                    'payment_url': f"{self.payment_url}{authority}",
                    'message': 'پرداخت آماده است'
                }
            else:
                # Error
                error_message = self._get_error_message(response_data.get('errors', {}).get('code'))
                payment.mark_as_failed(error_message, response_data)
                
                return {
                    'success': False,
                    'message': error_message,
                    'error_code': response_data.get('errors', {}).get('code')
                }
                
        except requests.RequestException as e:
            error_message = f"خطا در ارتباط با درگاه: {str(e)}"
            payment.mark_as_failed(error_message)
            logger.error(f"Zarinpal request error: {e}")
            
            return {
                'success': False,
                'message': error_message
            }
        except Exception as e:
            error_message = f"خطای غیرمنتظره: {str(e)}"
            payment.mark_as_failed(error_message)
            logger.error(f"Zarinpal unexpected error: {e}")
            
            return {
                'success': False,
                'message': error_message
            }
    
    def verify_payment(self, payment, request_data):
        """Verify Zarinpal payment"""
        try:
            authority = request_data.get('Authority')
            status = request_data.get('Status')
            
            if status != 'OK':
                payment.mark_as_failed("پرداخت توسط کاربر لغو شد", request_data)
                return {
                    'success': False,
                    'message': 'پرداخت لغو شد'
                }
            
            # Verify with Zarinpal
            verify_data = {
                'merchant_id': payment.gateway.merchant_id,
                'amount': payment.final_amount,
                'authority': authority
            }
            
            response = requests.post(
                f"{self.get_base_url()}PaymentVerification.json",
                json=verify_data,
                timeout=self.timeout
            )
            
            response_data = response.json()
            
            # Log verification
            payment.callback_log = {
                'request_data': request_data,
                'verify_response': response_data
            }
            payment.save()
            
            # Log attempt
            self.log_attempt(payment, response_data, response.status_code, "Payment verification")
            
            if response_data.get('data', {}).get('code') == 100:
                # Payment successful
                ref_id = response_data['data']['ref_id']
                card_pan = response_data['data'].get('card_pan', '')
                
                payment.mark_as_completed({
                    'reference_id': str(ref_id),
                    'card_pan': card_pan[-4:] if card_pan else '',
                    'authority': authority
                })
                
                return {
                    'success': True,
                    'reference_id': str(ref_id),
                    'message': 'پرداخت با موفقیت انجام شد'
                }
            else:
                # Payment failed
                error_message = self._get_error_message(response_data.get('data', {}).get('code'))
                payment.mark_as_failed(error_message, response_data)
                
                return {
                    'success': False,
                    'message': error_message
                }
                
        except requests.RequestException as e:
            error_message = f"خطا در تایید پرداخت: {str(e)}"
            payment.mark_as_failed(error_message)
            logger.error(f"Zarinpal verification error: {e}")
            
            return {
                'success': False,
                'message': error_message
            }
        except Exception as e:
            error_message = f"خطای غیرمنتظره در تایید: {str(e)}"
            payment.mark_as_failed(error_message)
            logger.error(f"Zarinpal verification unexpected error: {e}")
            
            return {
                'success': False,
                'message': error_message
            }
    
    def create_refund(self, payment, amount, reason):
        """Create Zarinpal refund"""
        try:
            if not payment.gateway_reference_id:
                return {
                    'success': False,
                    'message': 'شماره مرجع یافت نشد'
                }
            
            refund_data = {
                'merchant_id': payment.gateway.merchant_id,
                'amount': amount,
                'authority': payment.gateway_authority,
                'description': reason
            }
            
            response = requests.post(
                f"{self.get_base_url()}RefundRequest.json",
                json=refund_data,
                timeout=self.timeout
            )
            
            response_data = response.json()
            
            if response_data.get('data', {}).get('code') == 100:
                return {
                    'success': True,
                    'refund_id': response_data['data'].get('refund_id'),
                    'message': 'درخواست بازگشت وجه ثبت شد'
                }
            else:
                return {
                    'success': False,
                    'message': self._get_error_message(response_data.get('errors', {}).get('code')),
                    'response': response_data
                }
                
        except Exception as e:
            logger.error(f"Zarinpal refund error: {e}")
            return {
                'success': False,
                'message': f"خطا در بازگشت وجه: {str(e)}"
            }
    
    def _get_callback_url(self):
        """Get callback URL"""
        return f"{settings.FRONTEND_URL}/payment/callback/zarinpal/"
    
    def _get_error_message(self, error_code):
        """Get Persian error message"""
        error_messages = {
            -1: "اطلاعات ارسال شده ناقص است",
            -2: "IP یا مرچنت کد پذیرنده صحیح نیست",
            -3: "با توجه به محدودیت‌های شاپرک امکان پردازش وجود ندارد",
            -4: "سطح تایید پذیرنده پایین‌تر از سطح نقره‌ای است",
            -11: "درخواست مورد نظر یافت نشد",
            -12: "امکان ویرایش درخواست وجود ندارد",
            -21: "هیچ نوع عملیات مالی برای این تراکنش یافت نشد",
            -22: "تراکنش ناموفق است",
            -33: "رقم تراکنش با رقم پرداخت شده مطابقت ندارد",
            -34: "سقف تقسیم تراکنش از لحاظ تعداد یا رقم عبور کرده است",
            -40: "اجازه دسترسی به متد مورد نظر وجود ندارد",
            -41: "اطلاعات ارسال شده مربوط به AdditionalData غیرمعتبر است",
            -42: "مدت زمان معتبر طول عمر شناسه پرداخت باید بین ۳۰ دقیقه تا ۴۵ روز باشد",
            -54: "درخواست مورد نظر آرشیو شده است",
            101: "عملیات پرداخت موفق بوده و قبلا PaymentVerification تراکنش انجام شده است",
        }
        return error_messages.get(error_code, f"خطای غیرمنتظره (کد: {error_code})")


class MellatGateway(BasePaymentGateway):
    """Mellat Bank Payment Gateway"""
    
    def __init__(self):
        super().__init__()
        self.endpoint = "https://bpm.shaparak.ir/pgwchannel/services/pgw"
        self.payment_url = "https://bpm.shaparak.ir/pgwchannel/startpay.mellat"
    
    def prepare_payment(self, payment):
        """Prepare Mellat payment"""
        try:
            gateway = payment.gateway
            order_id = int(timezone.now().timestamp() * 1000)  # Unique order ID
            
            # Prepare request data
            request_data = {
                'terminalId': gateway.merchant_id,
                'userName': gateway.settings.get('username', ''),
                'userPassword': gateway.settings.get('password', ''),
                'orderId': order_id,
                'amount': payment.final_amount,
                'localDate': timezone.now().strftime('%Y%m%d'),
                'localTime': timezone.now().strftime('%H%M%S'),
                'additionalData': f"order_{payment.order.id}",
                'callBackUrl': self._get_callback_url(),
                'payerId': 0
            }
            
            # Log request
            payment.request_log = request_data
            payment.gateway_transaction_id = str(order_id)
            payment.save()
            
            # Create SOAP envelope
            soap_body = self._create_soap_request('bpPayRequest', request_data)
            
            # Send request
            response = requests.post(
                self.endpoint,
                data=soap_body,
                headers={'Content-Type': 'text/xml; charset=utf-8'},
                timeout=self.timeout
            )
            
            # Parse response
            if '0,' in response.text:
                parts = response.text.split(',')
                if parts[0] == '0':
                    ref_id = parts[1]
                    payment.gateway_authority = ref_id
                    payment.status = 'processing'
                    payment.save()
                    
                    return {
                        'success': True,
                        'authority': ref_id,
                        'payment_url': f"{self.payment_url}?RefId={ref_id}",
                        'message': 'پرداخت آماده است'
                    }
            
            # Handle error
            error_message = self._get_mellat_error_message(response.text)
            payment.mark_as_failed(error_message, {'response': response.text})
            
            return {
                'success': False,
                'message': error_message
            }
            
        except Exception as e:
            error_message = f"خطا در ارتباط با درگاه ملت: {str(e)}"
            payment.mark_as_failed(error_message)
            logger.error(f"Mellat request error: {e}")
            
            return {
                'success': False,
                'message': error_message
            }
    
    def verify_payment(self, payment, request_data):
        """Verify Mellat payment"""
        try:
            ref_id = request_data.get('RefId')
            res_code = request_data.get('ResCode')
            sale_order_id = request_data.get('SaleOrderId')
            sale_reference_id = request_data.get('SaleReferenceId')
            
            if res_code != '0':
                error_message = self._get_mellat_error_message(res_code)
                payment.mark_as_failed(error_message, request_data)
                return {
                    'success': False,
                    'message': error_message
                }
            
            # Verify payment
            gateway = payment.gateway
            verify_data = {
                'terminalId': gateway.merchant_id,
                'userName': gateway.settings.get('username', ''),
                'userPassword': gateway.settings.get('password', ''),
                'orderId': payment.gateway_transaction_id,
                'saleOrderId': sale_order_id,
                'saleReferenceId': sale_reference_id
            }
            
            soap_body = self._create_soap_request('bpVerifyRequest', verify_data)
            
            response = requests.post(
                self.endpoint,
                data=soap_body,
                headers={'Content-Type': 'text/xml; charset=utf-8'},
                timeout=self.timeout
            )
            
            if response.text.strip() == '0':
                # Payment successful
                payment.mark_as_completed({
                    'reference_id': sale_reference_id,
                    'sale_order_id': sale_order_id,
                    'ref_id': ref_id
                })
                
                return {
                    'success': True,
                    'reference_id': sale_reference_id,
                    'message': 'پرداخت با موفقیت انجام شد'
                }
            else:
                error_message = self._get_mellat_error_message(response.text)
                payment.mark_as_failed(error_message, {'verify_response': response.text})
                
                return {
                    'success': False,
                    'message': error_message
                }
                
        except Exception as e:
            error_message = f"خطا در تایید پرداخت ملت: {str(e)}"
            payment.mark_as_failed(error_message)
            logger.error(f"Mellat verification error: {e}")
            
            return {
                'success': False,
                'message': error_message
            }
    
    def _create_soap_request(self, method, data):
        """Create SOAP request for Mellat"""
        params = ''.join([f"<{k}>{v}</{k}>" for k, v in data.items()])
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:int="http://interfaces.core.sw.bps.com/">
            <soapenv:Header/>
            <soapenv:Body>
                <int:{method}>
                    {params}
                </int:{method}>
            </soapenv:Body>
        </soapenv:Envelope>"""
    
    def _get_callback_url(self):
        """Get callback URL"""
        return f"{settings.FRONTEND_URL}/payment/callback/mellat/"
    
    def _get_mellat_error_message(self, error_code):
        """Get Mellat error message"""
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
            '114': 'دارنده کارت مجاز به انجام این تراکنش نیست',
            '21': 'پذیرنده نامعتبر است',
            '23': 'خطای امنیتی رخ داده است',
            '24': 'اطلاعات کاربری پذیرنده نامعتبر است',
            '25': 'مبلغ نامعتبر است',
            '31': 'پاسخ نامعتبر است',
            '32': 'فرمت اطلاعات وارد شده صحیح نمی‌باشد',
            '33': 'حساب نامعتبر است',
            '34': 'خطای سیستمی',
            '35': 'تاریخ نامعتبر است',
            '41': 'شماره درخواست تکراری است',
            '42': 'تراکنش Sale یافت نشد',
            '43': 'قبلا درخواست Verify داده شده است',
            '44': 'درخواست Verify یافت نشد',
            '45': 'تراکنش Settle شده است',
            '46': 'تراکنش Settle نشده است',
            '47': 'تراکنش Settle یافت نشد',
            '48': 'تراکنش Reverse شده است',
            '49': 'تراکنش Refund یافت نشد',
            '412': 'شناسه قبض نادرست است',
            '413': 'شناسه پرداخت نادرست است',
            '414': 'سازمان صادر کننده قبض نامعتبر است',
            '415': 'زمان جلسه کاری به پایان رسیده است',
            '416': 'خطا در ثبت اطلاعات',
            '417': 'شناسه پرداخت کننده نامعتبر است',
            '418': 'اشکال در تعریف اطلاعات مشتری',
            '419': 'تعداد دفعات ورود اطلاعات از حد مجاز گذشته است',
            '421': 'IP نامعتبر است',
        }
        return error_messages.get(str(error_code), f"خطای درگاه ملت (کد: {error_code})")


class ParsianGateway(BasePaymentGateway):
    """Parsian Bank Payment Gateway"""
    
    def __init__(self):
        super().__init__()
        self.endpoint = "https://pec.shaparak.ir/NewIPGServices/Sale/SaleService.asmx"
        self.payment_url = "https://pec.shaparak.ir/NewIPG/?Token="
    
    def prepare_payment(self, payment):
        """Prepare Parsian payment"""
        # Implementation similar to Mellat with Parsian specific parameters
        pass
    
    def verify_payment(self, payment, request_data):
        """Verify Parsian payment"""
        # Implementation for Parsian verification
        pass


class SamanGateway(BasePaymentGateway):
    """Saman Bank Payment Gateway"""
    
    def __init__(self):
        super().__init__()
        self.endpoint = "https://sep.shaparak.ir/payments/"
        self.payment_url = "https://sep.shaparak.ir/OnlinePG/OnlinePG"
    
    def prepare_payment(self, payment):
        """Prepare Saman payment"""
        # Implementation for Saman gateway
        pass


class PaymentService:
    """Main payment service class"""
    
    @staticmethod
    def create_payment(order, gateway_name, customer_data):
        """Create a new payment"""
        try:
            gateway = PaymentGateway.objects.get(name=gateway_name, is_active=True)
            
            # Validate amount
            if not gateway.can_process_amount(order.total_amount):
                return {
                    'success': False,
                    'message': f'مبلغ باید بین {gateway.min_amount:,} تا {gateway.max_amount:,} ریال باشد'
                }
            
            # Create payment record
            payment = Payment.objects.create(
                order=order,
                gateway=gateway,
                user=order.user,
                customer_name=customer_data.get('name', ''),
                customer_email=customer_data.get('email', ''),
                customer_phone=customer_data.get('phone', ''),
                original_amount=order.total_amount,
                description=f"پرداخت سفارش شماره {order.id}"
            )
            
            # Prepare payment with gateway
            gateway_instance = PaymentGatewayFactory.create_gateway(gateway_name)
            result = gateway_instance.prepare_payment(payment)
            
            if result['success']:
                return {
                    'success': True,
                    'payment_id': str(payment.payment_id),
                    'payment_url': result['payment_url'],
                    'authority': result.get('authority'),
                    'message': result['message']
                }
            else:
                return result
                
        except PaymentGateway.DoesNotExist:
            return {
                'success': False,
                'message': 'درگاه پرداخت یافت نشد'
            }
        except Exception as e:
            logger.error(f"Payment creation error: {e}")
            return {
                'success': False,
                'message': f'خطا در ایجاد پرداخت: {str(e)}'
            }
    
    @staticmethod
    def verify_payment(payment_id, gateway_name, request_data):
        """Verify payment"""
        try:
            payment = Payment.objects.get(payment_id=payment_id)
            
            if payment.is_successful:
                return {
                    'success': True,
                    'message': 'پرداخت قبلاً تایید شده است',
                    'reference_id': payment.gateway_reference_id
                }
            
            gateway_instance = PaymentGatewayFactory.create_gateway(gateway_name)
            result = gateway_instance.verify_payment(payment, request_data)
            
            if result['success']:
                # Update order status
                payment.order.status = 'paid'
                payment.order.save()
                
                # Send notifications
                PaymentService._send_payment_notifications(payment)
            
            return result
            
        except Payment.DoesNotExist:
            return {
                'success': False,
                'message': 'پرداخت یافت نشد'
            }
        except Exception as e:
            logger.error(f"Payment verification error: {e}")
            return {
                'success': False,
                'message': f'خطا در تایید پرداخت: {str(e)}'
            }
    
    @staticmethod
    def _send_payment_notifications(payment):
        """Send payment success notifications"""
        try:
            # Send SMS notification
            from .sms_service import SMSService
            sms_service = SMSService()
            
            message = f"پرداخت شما با موفقیت انجام شد. شماره مرجع: {payment.gateway_reference_id}"
            sms_service.send_sms(payment.customer_phone, message)
            
            # Send email if available
            if payment.customer_email:
                # Implementation for email notification
                pass
                
        except Exception as e:
            logger.error(f"Notification sending error: {e}")
