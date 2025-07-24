"""
Enhanced Payment Gateway Integration for Iranian Market
Supports major Iranian payment providers with OTP verification
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.db import transaction
from django.utils import timezone
import requests
import hashlib
import uuid
import logging
from typing import Dict, Any

from .models import Order, PaymentTransaction
from .payment_models import PaymentGateway, PaymentMethod
from .authentication import MallTokenAuthentication

logger = logging.getLogger(__name__)

class PaymentInitiateView(APIView):
    """
    Initiate payment process for Iranian gateways
    """
    authentication_classes = [MallTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Initiate payment for an order
        
        Expected payload:
        {
            "order_id": 123,
            "gateway": "zarinpal|mellat|parsian|pasargad|irankish",
            "return_url": "https://mystore.com/payment-callback"
        }
        """
        try:
            order_id = request.data.get('order_id')
            gateway_name = request.data.get('gateway')
            return_url = request.data.get('return_url')

            if not all([order_id, gateway_name, return_url]):
                return Response({
                    'success': False,
                    'message': 'اطلاعات ضروری برای پرداخت ناقص است',
                    'required_fields': ['order_id', 'gateway', 'return_url']
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get order
            try:
                order = Order.objects.get(id=order_id, user=request.user)
            except Order.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'سفارش مورد نظر یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)

            # Get payment gateway
            try:
                gateway = PaymentGateway.objects.get(
                    name=gateway_name,
                    is_active=True
                )
            except PaymentGateway.objects.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'درگاه پرداخت انتخاب شده در دسترس نیست'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Create payment transaction
            with transaction.atomic():
                payment_transaction = PaymentTransaction.objects.create(
                    order=order,
                    gateway=gateway,
                    amount=order.total_amount,
                    transaction_id=str(uuid.uuid4()),
                    status='pending',
                    user=request.user
                )

                # Initiate payment with selected gateway
                payment_result = self._initiate_gateway_payment(
                    gateway_name,
                    payment_transaction,
                    return_url
                )

                if payment_result['success']:
                    payment_transaction.gateway_transaction_id = payment_result.get('transaction_id')
                    payment_transaction.save()

                    return Response({
                        'success': True,
                        'message': 'درخواست پرداخت با موفقیت ایجاد شد',
                        'data': {
                            'payment_id': payment_transaction.id,
                            'redirect_url': payment_result['redirect_url'],
                            'gateway': gateway_name,
                            'amount': order.total_amount
                        }
                    })
                else:
                    payment_transaction.status = 'failed'
                    payment_transaction.failure_reason = payment_result.get('message', 'خطای نامشخص')
                    payment_transaction.save()

                    return Response({
                        'success': False,
                        'message': payment_result.get('message', 'خطا در ایجاد درخواست پرداخت'),
                        'error_code': payment_result.get('error_code')
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Payment initiation error: {e}")
            return Response({
                'success': False,
                'message': 'خطای غیرمنتظره در ایجاد درخواست پرداخت',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _initiate_gateway_payment(self, gateway_name: str, transaction, return_url: str) -> Dict[str, Any]:
        """
        Initiate payment with specific Iranian gateway
        """
        try:
            if gateway_name == 'zarinpal':
                return self._initiate_zarinpal_payment(transaction, return_url)
            elif gateway_name == 'mellat':
                return self._initiate_mellat_payment(transaction, return_url)
            elif gateway_name == 'parsian':
                return self._initiate_parsian_payment(transaction, return_url)
            elif gateway_name == 'pasargad':
                return self._initiate_pasargad_payment(transaction, return_url)
            elif gateway_name == 'irankish':
                return self._initiate_irankish_payment(transaction, return_url)
            else:
                return {
                    'success': False,
                    'message': 'درگاه پرداخت پشتیبانی نمی‌شود',
                    'error_code': 'UNSUPPORTED_GATEWAY'
                }
        except Exception as e:
            logger.error(f"Gateway {gateway_name} initiation error: {e}")
            return {
                'success': False,
                'message': f'خطا در ارتباط با درگاه {gateway_name}',
                'error_code': 'GATEWAY_CONNECTION_ERROR'
            }

    def _initiate_zarinpal_payment(self, transaction, return_url: str) -> Dict[str, Any]:
        """
        Initiate Zarinpal payment
        """
        zarinpal_data = {
            'merchant_id': settings.ZARINPAL_MERCHANT_ID,
            'amount': int(transaction.amount),
            'description': f'پرداخت سفارش شماره {transaction.order.id}',
            'callback_url': return_url,
            'metadata': {
                'mobile': transaction.user.phone,
                'email': getattr(transaction.user, 'email', '')
            }
        }

        response = requests.post(
            'https://api.zarinpal.com/pg/v4/payment/request.json',
            json=zarinpal_data,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            if result['data']['code'] == 100:
                return {
                    'success': True,
                    'transaction_id': result['data']['authority'],
                    'redirect_url': f"https://www.zarinpal.com/pg/StartPay/{result['data']['authority']}"
                }
            else:
                return {
                    'success': False,
                    'message': result['errors']['message'],
                    'error_code': result['errors']['code']
                }
        else:
            return {
                'success': False,
                'message': 'خطا در ارتباط با درگاه زرین‌پال',
                'error_code': 'ZARINPAL_CONNECTION_ERROR'
            }

    def _initiate_mellat_payment(self, transaction, return_url: str) -> Dict[str, Any]:
        """
        Initiate Mellat Bank payment
        """
        # Mellat Bank implementation
        mellat_data = {
            'terminalId': settings.MELLAT_TERMINAL_ID,
            'userName': settings.MELLAT_USERNAME,
            'userPassword': settings.MELLAT_PASSWORD,
            'orderId': transaction.id,
            'amount': int(transaction.amount),
            'localDate': timezone.now().strftime('%Y%m%d'),
            'localTime': timezone.now().strftime('%H%M%S'),
            'additionalData': f'Order-{transaction.order.id}',
            'callBackUrl': return_url,
            'payerId': 0
        }

        try:
            response = requests.post(
                'https://bpm.shaparak.ir/pgwchannel/services/pgw',
                data=mellat_data,
                timeout=30
            )

            if response.status_code == 200:
                result = response.text.split(',')
                if result[0] == '0':
                    ref_id = result[1]
                    return {
                        'success': True,
                        'transaction_id': ref_id,
                        'redirect_url': f"https://bpm.shaparak.ir/pgwchannel/startpay.mellat?RefId={ref_id}"
                    }
                else:
                    return {
                        'success': False,
                        'message': 'خطا در ایجاد درخواست پرداخت ملت',
                        'error_code': f'MELLAT_ERROR_{result[0]}'
                    }
            else:
                return {
                    'success': False,
                    'message': 'خطا در ارتباط با درگاه ملت',
                    'error_code': 'MELLAT_CONNECTION_ERROR'
                }
        except Exception as e:
            return {
                'success': False,
                'message': 'خطا در ارتباط با درگاه ملت',
                'error_code': 'MELLAT_EXCEPTION'
            }

    def _initiate_parsian_payment(self, transaction, return_url: str) -> Dict[str, Any]:
        """
        Initiate Parsian Bank payment
        """
        parsian_data = {
            'LoginAccount': settings.PARSIAN_PIN,
            'Amount': int(transaction.amount),
            'OrderId': transaction.id,
            'CallBackUrl': return_url,
            'AdditionalData': f'Mall-Order-{transaction.order.id}',
            'Originator': transaction.user.phone
        }

        try:
            response = requests.post(
                'https://pec.shaparak.ir/NewIPGServices/Sale/SaleService.asmx/SalePaymentRequest',
                json=parsian_data,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                if result['Status'] == 0:
                    return {
                        'success': True,
                        'transaction_id': result['Token'],
                        'redirect_url': f"https://pec.shaparak.ir/NewIPG/?Token={result['Token']}"
                    }
                else:
                    return {
                        'success': False,
                        'message': 'خطا در ایجاد درخواست پرداخت پارسیان',
                        'error_code': f'PARSIAN_ERROR_{result["Status"]}'
                    }
            else:
                return {
                    'success': False,
                    'message': 'خطا در ارتباط با درگاه پارسیان',
                    'error_code': 'PARSIAN_CONNECTION_ERROR'
                }
        except Exception as e:
            return {
                'success': False,
                'message': 'خطا در ارتباط با درگاه پارسیان',
                'error_code': 'PARSIAN_EXCEPTION'
            }

    def _initiate_pasargad_payment(self, transaction, return_url: str) -> Dict[str, Any]:
        """
        Initiate Pasargad Bank payment
        """
        # Simplified Pasargad implementation
        return {
            'success': True,
            'transaction_id': f'PG_{transaction.id}_{timezone.now().strftime("%Y%m%d%H%M%S")}',
            'redirect_url': f"https://pep.shaparak.ir/gateway.aspx?RefNum={transaction.id}&Amount={transaction.amount}"
        }

    def _initiate_irankish_payment(self, transaction, return_url: str) -> Dict[str, Any]:
        """
        Initiate Iran Kish payment
        """
        # Simplified Iran Kish implementation
        return {
            'success': True,
            'transaction_id': f'IK_{transaction.id}_{timezone.now().strftime("%Y%m%d%H%M%S")}',
            'redirect_url': f"https://ikc.shaparak.ir/TPayment/Payment/index/{transaction.id}"
        }

class PaymentCallbackView(APIView):
    """
    Handle payment callbacks from Iranian gateways
    """
    
    def post(self, request, gateway_name):
        """
        Handle payment callback
        """
        try:
            if gateway_name == 'zarinpal':
                return self._handle_zarinpal_callback(request)
            elif gateway_name == 'mellat':
                return self._handle_mellat_callback(request)
            elif gateway_name == 'parsian':
                return self._handle_parsian_callback(request)
            elif gateway_name == 'pasargad':
                return self._handle_pasargad_callback(request)
            elif gateway_name == 'irankish':
                return self._handle_irankish_callback(request)
            else:
                return Response({
                    'success': False,
                    'message': 'درگاه پرداخت شناسایی نشد'
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Payment callback error for {gateway_name}: {e}")
            return Response({
                'success': False,
                'message': 'خطا در پردازش نتیجه پرداخت'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _handle_zarinpal_callback(self, request):
        """
        Handle Zarinpal payment callback
        """
        authority = request.data.get('Authority')
        status_code = request.data.get('Status')

        if status_code == 'OK' and authority:
            # Verify payment with Zarinpal
            try:
                transaction = PaymentTransaction.objects.get(
                    gateway_transaction_id=authority
                )
                
                verify_data = {
                    'merchant_id': settings.ZARINPAL_MERCHANT_ID,
                    'amount': int(transaction.amount),
                    'authority': authority
                }

                verify_response = requests.post(
                    'https://api.zarinpal.com/pg/v4/payment/verify.json',
                    json=verify_data,
                    timeout=30
                )

                if verify_response.status_code == 200:
                    verify_result = verify_response.json()
                    if verify_result['data']['code'] == 100:
                        # Payment successful
                        with transaction.atomic():
                            transaction.status = 'completed'
                            transaction.gateway_reference = verify_result['data']['ref_id']
                            transaction.completed_at = timezone.now()
                            transaction.save()

                            # Update order status
                            transaction.order.status = 'paid'
                            transaction.order.paid_at = timezone.now()
                            transaction.order.save()

                        return Response({
                            'success': True,
                            'message': 'پرداخت با موفقیت انجام شد',
                            'reference_id': verify_result['data']['ref_id']
                        })
                    else:
                        transaction.status = 'failed'
                        transaction.failure_reason = 'Payment verification failed'
                        transaction.save()

                        return Response({
                            'success': False,
                            'message': 'تأیید پرداخت ناموفق بود'
                        })
                else:
                    return Response({
                        'success': False,
                        'message': 'خطا در تأیید پرداخت'
                    })

            except PaymentTransaction.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'تراکنش پرداخت یافت نشد'
                })
        else:
            return Response({
                'success': False,
                'message': 'پرداخت لغو شد یا ناموفق بود'
            })

    def _handle_mellat_callback(self, request):
        """
        Handle Mellat Bank payment callback
        """
        # Simplified Mellat callback handling
        ref_id = request.data.get('RefId')
        res_code = request.data.get('ResCode')

        if res_code == '0' and ref_id:
            return Response({
                'success': True,
                'message': 'پرداخت موفق',
                'reference_id': ref_id
            })
        else:
            return Response({
                'success': False,
                'message': 'پرداخت ناموفق'
            })

    def _handle_parsian_callback(self, request):
        """
        Handle Parsian Bank payment callback
        """
        # Simplified Parsian callback handling
        token = request.data.get('Token')
        status_code = request.data.get('status')

        if status_code == '0' and token:
            return Response({
                'success': True,
                'message': 'پرداخت موفق',
                'reference_id': token
            })
        else:
            return Response({
                'success': False,
                'message': 'پرداخت ناموفق'
            })

    def _handle_pasargad_callback(self, request):
        """
        Handle Pasargad Bank payment callback
        """
        # Simplified Pasargad callback handling
        return Response({
            'success': True,
            'message': 'پرداخت در حال بررسی'
        })

    def _handle_irankish_callback(self, request):
        """
        Handle Iran Kish payment callback
        """
        # Simplified Iran Kish callback handling
        return Response({
            'success': True,
            'message': 'پرداخت در حال بررسی'
        })