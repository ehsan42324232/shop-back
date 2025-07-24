# shop/enhanced_payment_views_v2.py
"""
Mall Platform - Enhanced Payment Views with Gateway Integration
Complete payment processing with Iranian gateways
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.urls import reverse
import logging
import uuid

from .models import *
from .payment_models import Payment, PaymentTransaction
from .order_models import Order
from .payment_gateways import payment_service
from .serializers import PaymentSerializer

logger = logging.getLogger(__name__)

@api_view(['GET'])
def get_available_payment_gateways(request):
    """Get list of available payment gateways for the store"""
    try:
        store = get_object_or_404(Store, owner=request.user)
        
        # Get available gateways
        available_gateways = payment_service.get_available_gateways()
        
        # Get store's gateway configurations
        gateway_configs = []
        for gateway_name, gateway_instance in available_gateways.items():
            # Check if store has this gateway configured
            store_gateway = StorePaymentGateway.objects.filter(
                store=store,
                gateway_type=gateway_name,
                is_active=True
            ).first()
            
            if store_gateway:
                gateway_configs.append({
                    'name': gateway_name,
                    'display_name': store_gateway.display_name,
                    'description': store_gateway.description,
                    'icon': store_gateway.icon,
                    'fee_percentage': float(store_gateway.fee_percentage) if store_gateway.fee_percentage else 0,
                    'fee_fixed': float(store_gateway.fee_fixed) if store_gateway.fee_fixed else 0,
                    'min_amount': float(store_gateway.min_amount) if store_gateway.min_amount else 0,
                    'max_amount': float(store_gateway.max_amount) if store_gateway.max_amount else None,
                    'is_default': store_gateway.is_default
                })
        
        return Response({
            'success': True,
            'gateways': gateway_configs
        })
        
    except Exception as e:
        logger.error(f"Error getting payment gateways: {e}")
        return Response({
            'success': False,
            'message': 'خطا در دریافت درگاه‌های پرداخت'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_payment(request):
    """Initiate payment for an order"""
    try:
        order_id = request.data.get('order_id')
        gateway_name = request.data.get('gateway', 'zarinpal')
        
        if not order_id:
            return Response({
                'success': False,
                'message': 'شناسه سفارش الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get order
        order = get_object_or_404(Order, id=order_id, customer=request.user)
        
        if order.status != 'pending':
            return Response({
                'success': False,
                'message': 'وضعیت سفارش برای پرداخت مناسب نیست'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if there's already a pending payment
        pending_payment = Payment.objects.filter(
            order=order,
            status='pending'
        ).first()
        
        if pending_payment:
            # Cancel previous pending payment
            pending_payment.status = 'cancelled'
            pending_payment.save()
        
        # Get store's gateway configuration
        store_gateway = get_object_or_404(
            StorePaymentGateway,
            store=order.store,
            gateway_type=gateway_name,
            is_active=True
        )
        
        # Calculate final amount including fees
        base_amount = int(order.total_amount)
        gateway_fee = 0
        
        if store_gateway.fee_percentage:
            gateway_fee += base_amount * (store_gateway.fee_percentage / 100)
        if store_gateway.fee_fixed:
            gateway_fee += store_gateway.fee_fixed
            
        final_amount = base_amount + int(gateway_fee)
        
        # Check amount limits
        if store_gateway.min_amount and final_amount < store_gateway.min_amount:
            return Response({
                'success': False,
                'message': f'حداقل مبلغ پرداخت {store_gateway.min_amount:,} تومان است'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if store_gateway.max_amount and final_amount > store_gateway.max_amount:
            return Response({
                'success': False,
                'message': f'حداکثر مبلغ پرداخت {store_gateway.max_amount:,} تومان است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            # Create payment record
            payment = Payment.objects.create(
                order=order,
                amount=base_amount,
                gateway_fee=gateway_fee,
                total_amount=final_amount,
                gateway_type=gateway_name,
                status='pending',
                tracking_code=str(uuid.uuid4())[:16].upper()
            )
            
            # Generate callback URL
            callback_url = request.build_absolute_uri(
                reverse('payment_callback', kwargs={'payment_id': payment.id})
            )
            
            # Create payment request
            payment_result = payment_service.create_payment(
                gateway_name=gateway_name,
                amount=final_amount,
                order_id=str(order.id),
                callback_url=callback_url,
                description=f'پرداخت سفارش شماره {order.order_number}',
                mobile=getattr(request.user, 'mobile', ''),
                email=getattr(request.user, 'email', '')
            )
            
            if payment_result['success']:
                # Update payment with gateway response
                payment.gateway_token = payment_result.get('authority') or payment_result.get('token') or payment_result.get('ref_id')
                payment.gateway_url = payment_result['payment_url']
                payment.save()
                
                # Create transaction record
                PaymentTransaction.objects.create(
                    payment=payment,
                    transaction_type='initiate',
                    amount=final_amount,
                    gateway_response=payment_result,
                    status='success'
                )
                
                return Response({
                    'success': True,
                    'payment_id': payment.id,
                    'payment_url': payment_result['payment_url'],
                    'tracking_code': payment.tracking_code,
                    'amount': base_amount,
                    'gateway_fee': gateway_fee,
                    'total_amount': final_amount,
                    'message': 'درخواست پرداخت با موفقیت ایجاد شد'
                })
            else:
                # Update payment status
                payment.status = 'failed'
                payment.failure_reason = payment_result.get('message', 'خطای ناشناخته')
                payment.save()
                
                # Create transaction record
                PaymentTransaction.objects.create(
                    payment=payment,
                    transaction_type='initiate',
                    amount=final_amount,
                    gateway_response=payment_result,
                    status='failed'
                )
                
                return Response({
                    'success': False,
                    'message': payment_result.get('message', 'خطا در ایجاد درخواست پرداخت')
                }, status=status.HTTP_400_BAD_REQUEST)
                
    except Exception as e:
        logger.error(f"Payment initiation error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در پردازش درخواست پرداخت'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
def payment_callback(request, payment_id):
    """Handle payment gateway callback"""
    try:
        payment = get_object_or_404(Payment, id=payment_id)
        order = payment.order
        
        # Extract callback parameters based on gateway
        if payment.gateway_type == 'zarinpal':
            authority = request.GET.get('Authority') or request.POST.get('Authority')
            status_param = request.GET.get('Status') or request.POST.get('Status')
            
            if status_param == 'OK' and authority:
                # Verify payment
                verify_result = payment_service.verify_payment(
                    gateway_name='zarinpal',
                    authority=authority,
                    amount=int(payment.total_amount)
                )
                
                if verify_result['success'] and verify_result['verified']:
                    with transaction.atomic():
                        # Update payment
                        payment.status = 'completed'
                        payment.gateway_transaction_id = verify_result.get('ref_id')
                        payment.paid_at = timezone.now()
                        payment.save()
                        
                        # Update order
                        order.status = 'confirmed'
                        order.payment_status = 'paid'
                        order.save()
                        
                        # Create transaction record
                        PaymentTransaction.objects.create(
                            payment=payment,
                            transaction_type='verify',
                            amount=payment.total_amount,
                            gateway_response=verify_result,
                            status='success'
                        )
                        
                        # Send confirmation SMS/email
                        send_payment_confirmation(payment)
                        
                    return Response({
                        'success': True,
                        'message': 'پرداخت با موفقیت انجام شد',
                        'order_id': order.id,
                        'tracking_code': payment.tracking_code,
                        'ref_id': verify_result.get('ref_id')
                    })
                else:
                    # Payment verification failed
                    payment.status = 'failed'
                    payment.failure_reason = verify_result.get('message', 'تایید پرداخت ناموفق')
                    payment.save()
                    
                    PaymentTransaction.objects.create(
                        payment=payment,
                        transaction_type='verify',
                        amount=payment.total_amount,
                        gateway_response=verify_result,
                        status='failed'
                    )
                    
                    return Response({
                        'success': False,
                        'message': verify_result.get('message', 'تایید پرداخت ناموفق')
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                # Payment cancelled by user
                payment.status = 'cancelled'
                payment.failure_reason = 'کاربر از پرداخت منصرف شد'
                payment.save()
                
                return Response({
                    'success': False,
                    'message': 'پرداخت لغو شد'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        elif payment.gateway_type == 'mellat':
            ref_id = request.POST.get('RefId')
            res_code = request.POST.get('ResCode')
            sale_order_id = request.POST.get('SaleOrderId')
            sale_reference_id = request.POST.get('SaleReferenceId')
            
            if res_code == '0' and sale_reference_id:
                verify_result = payment_service.verify_payment(
                    gateway_name='mellat',
                    ref_id=ref_id,
                    sale_order_id=sale_order_id,
                    sale_reference_id=sale_reference_id
                )
                
                if verify_result['success'] and verify_result['verified']:
                    with transaction.atomic():
                        payment.status = 'completed'
                        payment.gateway_transaction_id = sale_reference_id
                        payment.paid_at = timezone.now()
                        payment.save()
                        
                        order.status = 'confirmed'
                        order.payment_status = 'paid'
                        order.save()
                        
                        PaymentTransaction.objects.create(
                            payment=payment,
                            transaction_type='verify',
                            amount=payment.total_amount,
                            gateway_response=verify_result,
                            status='success'
                        )
                        
                        send_payment_confirmation(payment)
                        
                    return Response({
                        'success': True,
                        'message': 'پرداخت با موفقیت انجام شد',
                        'order_id': order.id,
                        'tracking_code': payment.tracking_code,
                        'ref_id': sale_reference_id
                    })
                    
        elif payment.gateway_type == 'saman':
            ref_num = request.POST.get('RefNum')
            res_num = request.POST.get('ResNum')
            state = request.POST.get('State')
            
            if state == 'OK' and ref_num:
                verify_result = payment_service.verify_payment(
                    gateway_name='saman',
                    ref_num=ref_num,
                    order_id=str(order.id)
                )
                
                if verify_result['success'] and verify_result['verified']:
                    with transaction.atomic():
                        payment.status = 'completed'
                        payment.gateway_transaction_id = ref_num
                        payment.paid_at = timezone.now()
                        payment.save()
                        
                        order.status = 'confirmed'
                        order.payment_status = 'paid'
                        order.save()
                        
                        PaymentTransaction.objects.create(
                            payment=payment,
                            transaction_type='verify',
                            amount=payment.total_amount,
                            gateway_response=verify_result,
                            status='success'
                        )
                        
                        send_payment_confirmation(payment)
                        
                    return Response({
                        'success': True,
                        'message': 'پرداخت با موفقیت انجام شد',
                        'order_id': order.id,
                        'tracking_code': payment.tracking_code,
                        'ref_id': ref_num
                    })
        
        # If we reach here, payment failed
        payment.status = 'failed'
        payment.failure_reason = 'خطا در تایید پرداخت'
        payment.save()
        
        return Response({
            'success': False,
            'message': 'خطا در تایید پرداخت'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Payment callback error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در پردازش نتیجه پرداخت'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_payment_status(request, payment_id):
    """Check payment status"""
    try:
        payment = get_object_or_404(Payment, id=payment_id)
        
        # Verify user access
        if payment.order.customer != request.user:
            return Response({
                'success': False,
                'message': 'شما به این پرداخت دسترسی ندارید'
            }, status=status.HTTP_403_FORBIDDEN)
        
        return Response({
            'success': True,
            'payment': {
                'id': payment.id,
                'status': payment.status,
                'amount': float(payment.amount),
                'gateway_fee': float(payment.gateway_fee),
                'total_amount': float(payment.total_amount),
                'gateway_type': payment.gateway_type,
                'tracking_code': payment.tracking_code,
                'gateway_transaction_id': payment.gateway_transaction_id,
                'created_at': payment.created_at,
                'paid_at': payment.paid_at,
                'failure_reason': payment.failure_reason
            }
        })
        
    except Exception as e:
        logger.error(f"Check payment status error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در بررسی وضعیت پرداخت'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_payment_history(request):
    """Get user's payment history"""
    try:
        payments = Payment.objects.filter(
            order__customer=request.user
        ).select_related('order').order_by('-created_at')
        
        # Pagination
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        start = (page - 1) * per_page
        end = start + per_page
        
        total = payments.count()
        payments_page = payments[start:end]
        
        payment_data = []
        for payment in payments_page:
            payment_data.append({
                'id': payment.id,
                'order_id': payment.order.id,
                'order_number': payment.order.order_number,
                'store_name': payment.order.store.name,
                'amount': float(payment.amount),
                'gateway_fee': float(payment.gateway_fee),
                'total_amount': float(payment.total_amount),
                'gateway_type': payment.gateway_type,
                'status': payment.status,
                'tracking_code': payment.tracking_code,
                'gateway_transaction_id': payment.gateway_transaction_id,
                'created_at': payment.created_at,
                'paid_at': payment.paid_at,
                'failure_reason': payment.failure_reason
            })
        
        return Response({
            'success': True,
            'payments': payment_data,
            'pagination': {
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        logger.error(f"Payment history error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در دریافت تاریخچه پرداخت‌ها'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def refund_payment(request, payment_id):
    """Process payment refund (store owner only)"""
    try:
        payment = get_object_or_404(Payment, id=payment_id)
        
        # Check if user is store owner
        if payment.order.store.owner != request.user:
            return Response({
                'success': False,
                'message': 'شما مجاز به این عملیات نیستید'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if payment.status != 'completed':
            return Response({
                'success': False,
                'message': 'تنها پرداخت‌های موفق قابل بازگشت هستند'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        refund_amount = request.data.get('amount')
        reason = request.data.get('reason', 'درخواست فروشنده')
        
        if not refund_amount:
            refund_amount = payment.amount
        else:
            refund_amount = float(refund_amount)
            
        if refund_amount > payment.amount:
            return Response({
                'success': False,
                'message': 'مبلغ بازگشت نمی‌تواند بیشتر از مبلغ پرداخت باشد'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if already refunded
        existing_refund = PaymentRefund.objects.filter(
            payment=payment,
            status__in=['pending', 'completed']
        ).first()
        
        if existing_refund:
            return Response({
                'success': False,
                'message': 'این پرداخت قبلاً بازگشت داده شده است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            # Create refund record
            refund = PaymentRefund.objects.create(
                payment=payment,
                amount=refund_amount,
                reason=reason,
                status='pending',
                requested_by=request.user
            )
            
            # Create transaction record
            PaymentTransaction.objects.create(
                payment=payment,
                transaction_type='refund_request',
                amount=refund_amount,
                gateway_response={'reason': reason},
                status='pending'
            )
            
            # Update order status if full refund
            if refund_amount == payment.amount:
                payment.order.status = 'cancelled'
                payment.order.payment_status = 'refunded'
                payment.order.save()
        
        return Response({
            'success': True,
            'refund_id': refund.id,
            'message': 'درخواست بازگشت وجه ثبت شد'
        })
        
    except Exception as e:
        logger.error(f"Payment refund error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در پردازش درخواست بازگشت وجه'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def send_payment_confirmation(payment):
    """Send payment confirmation via SMS and email"""
    try:
        from .enhanced_sms_service import sms_service
        
        # Send SMS to customer
        customer = payment.order.customer
        if hasattr(customer, 'mobile') and customer.mobile:
            message = f"""سلام {customer.get_full_name()}
پرداخت شما با موفقیت انجام شد.
شماره سفارش: {payment.order.order_number}
مبلغ: {payment.amount:,} تومان
کد پیگیری: {payment.tracking_code}
فروشگاه: {payment.order.store.name}"""
            
            sms_service.send_sms(
                phone_number=customer.mobile,
                message=message,
                template_type='payment_success'
            )
        
        # Send email if available
        if hasattr(customer, 'email') and customer.email:
            # Email sending logic here
            pass
            
    except Exception as e:
        logger.error(f"Error sending payment confirmation: {e}")


# Additional models needed for payment gateway configuration
class StorePaymentGateway(models.Model):
    """Store-specific payment gateway configuration"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='payment_gateways')
    gateway_type = models.CharField(max_length=50, choices=[
        ('zarinpal', 'زرین‌پال'),
        ('mellat', 'بانک ملت'),
        ('saman', 'بانک سامان'),
        ('parsian', 'بانک پارسیان'),
        ('pasargad', 'بانک پاسارگاد')
    ])
    display_name = models.CharField(max_length=100, verbose_name='نام نمایشی')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    icon = models.ImageField(upload_to='payment_gateways/', blank=True, verbose_name='آیکون')
    
    # Gateway configuration
    merchant_id = models.CharField(max_length=100, verbose_name='شناسه پذیرنده')
    username = models.CharField(max_length=100, blank=True, verbose_name='نام کاربری')
    password = models.CharField(max_length=100, blank=True, verbose_name='رمز عبور')
    
    # Fee configuration
    fee_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='درصد کارمزد')
    fee_fixed = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='کارمزد ثابت')
    
    # Limits
    min_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='حداقل مبلغ')
    max_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='حداکثر مبلغ')
    
    # Status
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    is_default = models.BooleanField(default=False, verbose_name='پیش‌فرض')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['store', 'gateway_type']
        verbose_name = 'درگاه پرداخت فروشگاه'
        verbose_name_plural = 'درگاه‌های پرداخت فروشگاه'


class PaymentRefund(models.Model):
    """Payment refund tracking"""
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='refunds')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='مبلغ بازگشت')
    reason = models.TextField(verbose_name='دلیل بازگشت')
    status = models.CharField(max_length=20, choices=[
        ('pending', 'در انتظار'),
        ('processing', 'در حال پردازش'),
        ('completed', 'تکمیل شده'),
        ('failed', 'ناموفق'),
        ('cancelled', 'لغو شده')
    ], default='pending', verbose_name='وضعیت')
    
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='درخواست‌کننده')
    processed_at = models.DateTimeField(blank=True, null=True, verbose_name='زمان پردازش')
    gateway_refund_id = models.CharField(max_length=100, blank=True, verbose_name='شناسه بازگشت درگاه')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'بازگشت وجه'
        verbose_name_plural = 'بازگشت‌های وجه'
