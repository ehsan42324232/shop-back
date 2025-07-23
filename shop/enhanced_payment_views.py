# shop/enhanced_payment_views.py
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from django.conf import settings
import logging
import uuid

from .payment_models import Payment, PaymentGateway, Refund, PaymentSettings
from .payment_services import PaymentService, PaymentGatewayFactory
from .order_models import Order
from .serializers import PaymentSerializer, RefundSerializer
from .utils import create_response, log_user_activity

logger = logging.getLogger('payment')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_payment(request):
    """
    Initiate payment for an order
    """
    try:
        data = request.data
        order_id = data.get('order_id')
        gateway_name = data.get('gateway', 'zarinpal')
        
        # Validate required fields
        if not order_id:
            return create_response(
                success=False,
                message='شناسه سفارش الزامی است',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Get order
        order = get_object_or_404(Order, id=order_id, user=request.user)
        
        # Check if order can be paid
        if order.status != 'pending':
            return create_response(
                success=False,
                message='این سفارش قابل پرداخت نیست',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        if order.total_amount <= 0:
            return create_response(
                success=False,
                message='مبلغ سفارش معتبر نیست',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Check for existing pending payment
        existing_payment = Payment.objects.filter(
            order=order,
            status='pending'
        ).first()
        
        if existing_payment and not existing_payment.is_expired:
            return create_response(
                success=False,
                message='پرداخت در حال انتظار وجود دارد',
                data={
                    'payment_id': str(existing_payment.payment_id),
                    'expires_at': existing_payment.expires_at.isoformat()
                },
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Prepare customer data
        customer_data = {
            'name': data.get('customer_name', f"{request.user.first_name} {request.user.last_name}".strip()),
            'email': data.get('customer_email', request.user.email or ''),
            'phone': data.get('customer_phone', getattr(request.user, 'phone', ''))
        }
        
        # Create payment
        with transaction.atomic():
            result = PaymentService.create_payment(order, gateway_name, customer_data)
            
            if result['success']:
                # Log activity
                log_user_activity(
                    request.user,
                    'payment_initiated',
                    f"پرداخت سفارش {order.id} آغاز شد",
                    {'order_id': order.id, 'gateway': gateway_name}
                )
                
                return create_response(
                    success=True,
                    message='پرداخت با موفقیت آغاز شد',
                    data=result,
                    status_code=status.HTTP_201_CREATED
                )
            else:
                return create_response(
                    success=False,
                    message=result['message'],
                    status_code=status.HTTP_400_BAD_REQUEST
                )
                
    except Exception as e:
        logger.error(f"Payment initiation error: {e}")
        return create_response(
            success=False,
            message='خطا در آغاز پرداخت',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def verify_payment(request):
    """
    Verify payment callback from gateway
    """
    try:
        data = request.data
        payment_id = data.get('payment_id')
        gateway_name = data.get('gateway')
        
        if not payment_id or not gateway_name:
            return create_response(
                success=False,
                message='اطلاعات پرداخت ناقص است',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify payment
        with transaction.atomic():
            result = PaymentService.verify_payment(payment_id, gateway_name, data)
            
            if result['success']:
                # Get payment for logging
                payment = Payment.objects.get(payment_id=payment_id)
                
                log_user_activity(
                    payment.user,
                    'payment_completed',
                    f"پرداخت سفارش {payment.order.id} تکمیل شد",
                    {
                        'order_id': payment.order.id,
                        'reference_id': result.get('reference_id'),
                        'amount': payment.final_amount
                    }
                )
                
                return create_response(
                    success=True,
                    message=result['message'],
                    data={
                        'reference_id': result.get('reference_id'),
                        'order_id': payment.order.id,
                        'amount': payment.formatted_amount
                    },
                    status_code=status.HTTP_200_OK
                )
            else:
                return create_response(
                    success=False,
                    message=result['message'],
                    status_code=status.HTTP_400_BAD_REQUEST
                )
                
    except Payment.DoesNotExist:
        return create_response(
            success=False,
            message='پرداخت یافت نشد',
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Payment verification error: {e}")
        return create_response(
            success=False,
            message='خطا در تایید پرداخت',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_status(request, payment_id):
    """
    Get payment status
    """
    try:
        payment = get_object_or_404(Payment, payment_id=payment_id, user=request.user)
        
        serializer = PaymentSerializer(payment)
        
        return create_response(
            success=True,
            message='وضعیت پرداخت',
            data=serializer.data,
            status_code=status.HTTP_200_OK
        )
        
    except Exception as e:
        logger.error(f"Payment status error: {e}")
        return create_response(
            success=False,
            message='خطا در دریافت وضعیت پرداخت',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_payments(request):
    """
    Get user payments list
    """
    try:
        payments = Payment.objects.filter(user=request.user).order_by('-created_at')
        
        # Pagination
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated_payments = payments[start:end]
        total_count = payments.count()
        
        serializer = PaymentSerializer(paginated_payments, many=True)
        
        return create_response(
            success=True,
            message='لیست پرداخت‌ها',
            data={
                'payments': serializer.data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': (total_count + page_size - 1) // page_size
                }
            },
            status_code=status.HTTP_200_OK
        )
        
    except Exception as e:
        logger.error(f"User payments error: {e}")
        return create_response(
            success=False,
            message='خطا در دریافت پرداخت‌ها',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_refund(request, payment_id):
    """
    Request payment refund
    """
    try:
        data = request.data
        reason = data.get('reason', '')
        amount = data.get('amount')
        
        payment = get_object_or_404(Payment, payment_id=payment_id, user=request.user)
        
        # Validate payment
        if not payment.is_successful:
            return create_response(
                success=False,
                message='تنها پرداخت‌های موفق قابل بازگشت هستند',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if already refunded
        if payment.refunds.filter(status='completed').exists():
            return create_response(
                success=False,
                message='این پرداخت قبلاً بازگشت داده شده است',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate amount
        if not amount:
            amount = payment.original_amount
        
        if amount > payment.original_amount:
            return create_response(
                success=False,
                message='مبلغ بازگشت نمی‌تواند بیشتر از مبلغ پرداختی باشد',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Check for existing pending refund
        existing_refund = payment.refunds.filter(status='pending').first()
        if existing_refund:
            return create_response(
                success=False,
                message='درخواست بازگشت در انتظار بررسی است',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Create refund request
        with transaction.atomic():
            refund = Refund.objects.create(
                payment=payment,
                amount=amount,
                reason=reason,
                requested_by=request.user,
                status='pending'
            )
            
            # Check if auto-refund is enabled
            settings_obj = PaymentSettings.get_settings()
            if settings_obj.auto_refund_enabled and amount <= payment.original_amount:
                try:
                    # Process refund automatically
                    gateway_instance = PaymentGatewayFactory.create_gateway(payment.gateway.name)
                    refund_result = gateway_instance.create_refund(payment, amount, reason)
                    
                    if refund_result['success']:
                        refund.status = 'completed'
                        refund.gateway_refund_id = refund_result.get('refund_id', '')
                        refund.gateway_response = refund_result
                        refund.processed_at = timezone.now()
                        refund.save()
                        
                        message = 'بازگشت وجه با موفقیت انجام شد'
                    else:
                        refund.status = 'failed'
                        refund.gateway_response = refund_result
                        refund.save()
                        
                        message = f'خطا در بازگشت وجه: {refund_result["message"]}'
                except Exception as e:
                    logger.error(f"Auto refund error: {e}")
                    message = 'درخواست بازگشت ثبت شد و در انتظار بررسی است'
            else:
                message = 'درخواست بازگشت وجه ثبت شد و در انتظار بررسی مدیر است'
            
            # Log activity
            log_user_activity(
                request.user,
                'refund_requested',
                f"درخواست بازگشت وجه برای پرداخت {payment.payment_id}",
                {
                    'payment_id': str(payment.payment_id),
                    'amount': amount,
                    'reason': reason
                }
            )
            
            serializer = RefundSerializer(refund)
            
            return create_response(
                success=True,
                message=message,
                data=serializer.data,
                status_code=status.HTTP_201_CREATED
            )
            
    except Exception as e:
        logger.error(f"Refund request error: {e}")
        return create_response(
            success=False,
            message='خطا در درخواست بازگشت وجه',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def available_gateways(request):
    """
    Get list of available payment gateways
    """
    try:
        gateways = PaymentGateway.objects.filter(is_active=True).order_by('display_name')
        
        gateway_data = []
        for gateway in gateways:
            gateway_data.append({
                'name': gateway.name,
                'display_name': gateway.display_name,
                'min_amount': gateway.min_amount,
                'max_amount': gateway.max_amount,
                'fixed_fee': gateway.fixed_fee,
                'percentage_fee': float(gateway.percentage_fee),
                'logo_url': gateway.settings.get('logo_url', ''),
                'description': gateway.settings.get('description', '')
            })
        
        return create_response(
            success=True,
            message='درگاه‌های پرداخت موجود',
            data={'gateways': gateway_data},
            status_code=status.HTTP_200_OK
        )
        
    except Exception as e:
        logger.error(f"Available gateways error: {e}")
        return create_response(
            success=False,
            message='خطا در دریافت درگاه‌های پرداخت',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def retry_payment(request, payment_id):
    """
    Retry failed payment
    """
    try:
        payment = get_object_or_404(Payment, payment_id=payment_id, user=request.user)
        
        if not payment.can_retry():
            return create_response(
                success=False,
                message='این پرداخت قابل تکرار نیست',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Check retry limit
        retry_count = payment.attempts.count()
        settings_obj = PaymentSettings.get_settings()
        
        if retry_count >= settings_obj.retry_attempts:
            return create_response(
                success=False,
                message='تعداد تلاش‌های مجاز تمام شده است',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Retry payment
        gateway_instance = PaymentGatewayFactory.create_gateway(payment.gateway.name)
        result = gateway_instance.prepare_payment(payment)
        
        if result['success']:
            return create_response(
                success=True,
                message='پرداخت مجدد آماده است',
                data={
                    'payment_url': result['payment_url'],
                    'authority': result.get('authority')
                },
                status_code=status.HTTP_200_OK
            )
        else:
            return create_response(
                success=False,
                message=result['message'],
                status_code=status.HTTP_400_BAD_REQUEST
            )
            
    except Exception as e:
        logger.error(f"Payment retry error: {e}")
        return create_response(
            success=False,
            message='خطا در تکرار پرداخت',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_receipt(request, payment_id):
    """
    Get payment receipt/invoice
    """
    try:
        payment = get_object_or_404(Payment, payment_id=payment_id, user=request.user)
        
        if not payment.is_successful:
            return create_response(
                success=False,
                message='رسید تنها برای پرداخت‌های موفق قابل دریافت است',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        receipt_data = {
            'payment_id': str(payment.payment_id),
            'reference_id': payment.gateway_reference_id,
            'order_id': payment.order.id,
            'gateway_name': payment.gateway.display_name,
            'amount': payment.original_amount,
            'gateway_fee': payment.gateway_fee,
            'total_amount': payment.final_amount,
            'customer_name': payment.customer_name,
            'customer_phone': payment.customer_phone,
            'paid_at': payment.paid_at.isoformat() if payment.paid_at else None,
            'card_pan': payment.gateway_card_pan,
            'status': payment.get_status_display(),
            'order_items': [
                {
                    'product_name': item.product_instance.product.name,
                    'quantity': item.quantity,
                    'price': item.price,
                    'total': item.total_price
                }
                for item in payment.order.items.all()
            ]
        }
        
        return create_response(
            success=True,
            message='رسید پرداخت',
            data=receipt_data,
            status_code=status.HTTP_200_OK
        )
        
    except Exception as e:
        logger.error(f"Payment receipt error: {e}")
        return create_response(
            success=False,
            message='خطا در دریافت رسید',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_gateway_fee(request):
    """
    Calculate payment gateway fee
    """
    try:
        data = request.data
        amount = data.get('amount', 0)
        gateway_name = data.get('gateway', 'zarinpal')
        
        if amount <= 0:
            return create_response(
                success=False,
                message='مبلغ معتبر نیست',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        gateway = get_object_or_404(PaymentGateway, name=gateway_name, is_active=True)
        
        if not gateway.can_process_amount(amount):
            return create_response(
                success=False,
                message=f'مبلغ باید بین {gateway.min_amount:,} تا {gateway.max_amount:,} ریال باشد',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        fee = gateway.calculate_fee(amount)
        total = amount + fee
        
        return create_response(
            success=True,
            message='محاسبه کارمزد',
            data={
                'amount': amount,
                'gateway_fee': fee,
                'total_amount': total,
                'gateway_name': gateway.display_name,
                'fee_details': {
                    'fixed_fee': gateway.fixed_fee,
                    'percentage_fee': float(gateway.percentage_fee)
                }
            },
            status_code=status.HTTP_200_OK
        )
        
    except PaymentGateway.DoesNotExist:
        return create_response(
            success=False,
            message='درگاه پرداخت یافت نشد',
            status_code=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Fee calculation error: {e}")
        return create_response(
            success=False,
            message='خطا در محاسبه کارمزد',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Admin views for payment management
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_payments_list(request):
    """
    Admin view for payments list
    """
    # Check admin permission
    if not request.user.is_staff:
        return create_response(
            success=False,
            message='دسترسی محدود',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        payments = Payment.objects.all().order_by('-created_at')
        
        # Filters
        status_filter = request.GET.get('status')
        gateway_filter = request.GET.get('gateway')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        if status_filter:
            payments = payments.filter(status=status_filter)
        
        if gateway_filter:
            payments = payments.filter(gateway__name=gateway_filter)
        
        if date_from:
            payments = payments.filter(created_at__date__gte=date_from)
        
        if date_to:
            payments = payments.filter(created_at__date__lte=date_to)
        
        # Pagination
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 50))
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated_payments = payments[start:end]
        total_count = payments.count()
        
        serializer = PaymentSerializer(paginated_payments, many=True)
        
        # Statistics
        stats = {
            'total_payments': payments.count(),
            'successful_payments': payments.filter(status='completed').count(),
            'failed_payments': payments.filter(status='failed').count(),
            'pending_payments': payments.filter(status='pending').count(),
            'total_amount': sum(p.final_amount for p in payments.filter(status='completed')),
        }
        
        return create_response(
            success=True,
            message='لیست پرداخت‌ها',
            data={
                'payments': serializer.data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': (total_count + page_size - 1) // page_size
                },
                'statistics': stats
            },
            status_code=status.HTTP_200_OK
        )
        
    except Exception as e:
        logger.error(f"Admin payments list error: {e}")
        return create_response(
            success=False,
            message='خطا در دریافت لیست پرداخت‌ها',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_manual_verify(request, payment_id):
    """
    Admin manual payment verification
    """
    if not request.user.is_staff:
        return create_response(
            success=False,
            message='دسترسی محدود',
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    try:
        data = request.data
        notes = data.get('admin_notes', '')
        
        payment = get_object_or_404(Payment, payment_id=payment_id)
        
        with transaction.atomic():
            payment.mark_as_completed({
                'manual_verification': True,
                'admin_user_id': request.user.id,
                'verification_time': timezone.now().isoformat()
            })
            
            payment.is_manual_verification = True
            payment.admin_notes = notes
            payment.save()
            
            # Update order status
            payment.order.status = 'paid'
            payment.order.save()
            
            # Log activity
            log_user_activity(
                request.user,
                'manual_payment_verification',
                f"تایید دستی پرداخت {payment.payment_id}",
                {
                    'payment_id': str(payment.payment_id),
                    'order_id': payment.order.id,
                    'notes': notes
                }
            )
        
        return create_response(
            success=True,
            message='پرداخت به صورت دستی تایید شد',
            status_code=status.HTTP_200_OK
        )
        
    except Exception as e:
        logger.error(f"Manual verification error: {e}")
        return create_response(
            success=False,
            message='خطا در تایید دستی',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
