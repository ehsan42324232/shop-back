from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.http import JsonResponse, HttpResponseRedirect
from .payment_service import PaymentService
from .order_models import Order
import json
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_payment(request):
    """Create payment request for an order"""
    try:
        data = request.data
        order_id = data.get('order_id')
        gateway_type = data.get('gateway', 'zarinpal')
        
        if not order_id:
            return Response({
                'success': False,
                'message': 'شناسه سفارش الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get order
        try:
            order = Order.objects.get(id=order_id, store__owner=request.user)
        except Order.DoesNotExist:
            return Response({
                'success': False,
                'message': 'سفارش یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check order status
        if order.payment_status == 'paid':
            return Response({
                'success': False,
                'message': 'این سفارش قبلاً پرداخت شده است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create payment request
        payment_service = PaymentService()
        result = payment_service.create_payment_request(order, gateway_type)
        
        if result['success']:
            # Update order status
            order.payment_method = gateway_type
            order.save()
            
            return Response({
                'success': True,
                'message': result['message'],
                'data': {
                    'payment_url': result['payment_url'],
                    'gateway': gateway_type,
                    'order_number': order.order_number,
                    'amount': float(order.total_amount)
                }
            })
        else:
            return Response({
                'success': False,
                'message': result['error']
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.error(f"Payment creation error: {str(e)}")
        return Response({
            'success': False,
            'message': 'خطای سرور در ایجاد پرداخت'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class ZarinpalCallbackView(View):
    """Handle Zarinpal payment callback"""
    
    def get(self, request):
        try:
            authority = request.GET.get('Authority')
            status_param = request.GET.get('Status')
            
            if not authority:
                return HttpResponseRedirect('/payment/failed/?reason=no_authority')
            
            if status_param != 'OK':
                return HttpResponseRedirect('/payment/failed/?reason=cancelled')
            
            # Find order by authority (stored in cache)
            from django.core.cache import cache
            
            # Search through cache for matching authority
            order_id = None
            for key in cache._cache.keys():
                if key.startswith('payment_'):
                    payment_info = cache.get(key)
                    if payment_info and payment_info.get('authority') == authority:
                        order_id = payment_info['order_id']
                        break
            
            if not order_id:
                return HttpResponseRedirect('/payment/failed/?reason=order_not_found')
            
            # Get order
            try:
                order = Order.objects.get(id=order_id)
            except Order.DoesNotExist:
                return HttpResponseRedirect('/payment/failed/?reason=invalid_order')
            
            # Verify payment
            payment_service = PaymentService()
            result = payment_service.verify_payment(
                order_id=order_id,
                authority=authority,
                gateway_type='zarinpal'
            )
            
            if result['success']:
                # Update order
                order.payment_status = 'paid'
                order.transaction_id = result.get('ref_id', '')
                order.save()
                
                # TODO: Send SMS confirmation to customer
                # TODO: Update product inventory
                
                return HttpResponseRedirect(f'/payment/success/?order={order.order_number}')
            else:
                return HttpResponseRedirect(f'/payment/failed/?reason=verification_failed')
                
        except Exception as e:
            logger.error(f"Zarinpal callback error: {str(e)}")
            return HttpResponseRedirect('/payment/failed/?reason=server_error')

@method_decorator(csrf_exempt, name='dispatch')
class MellatCallbackView(View):
    """Handle Mellat Bank payment callback"""
    
    def post(self, request):
        try:
            ref_id = request.POST.get('RefId')
            sale_order_id = request.POST.get('SaleOrderId')
            sale_reference_id = request.POST.get('SaleReferenceId')
            res_code = request.POST.get('ResCode')
            
            if res_code != '0':
                return HttpResponseRedirect('/payment/failed/?reason=payment_failed')
            
            if not all([ref_id, sale_order_id, sale_reference_id]):
                return HttpResponseRedirect('/payment/failed/?reason=missing_params')
            
            # Get order
            try:
                order = Order.objects.get(id=sale_order_id)
            except Order.DoesNotExist:
                return HttpResponseRedirect('/payment/failed/?reason=invalid_order')
            
            # Verify payment
            payment_service = PaymentService()
            result = payment_service.verify_payment(
                order_id=sale_order_id,
                ref_id=sale_reference_id,
                gateway_type='mellat'
            )
            
            if result['success']:
                # Update order
                order.payment_status = 'paid'
                order.transaction_id = sale_reference_id
                order.save()
                
                return HttpResponseRedirect(f'/payment/success/?order={order.order_number}')
            else:
                return HttpResponseRedirect('/payment/failed/?reason=verification_failed')
                
        except Exception as e:
            logger.error(f"Mellat callback error: {str(e)}")
            return HttpResponseRedirect('/payment/failed/?reason=server_error')

@api_view(['GET'])
@permission_classes([AllowAny])
def payment_status(request):
    """Get payment status for an order"""
    try:
        order_number = request.GET.get('order')
        
        if not order_number:
            return Response({
                'success': False,
                'message': 'شماره سفارش الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            order = Order.objects.get(order_number=order_number)
        except Order.DoesNotExist:
            return Response({
                'success': False,
                'message': 'سفارش یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            'success': True,
            'data': {
                'order_number': order.order_number,
                'payment_status': order.payment_status,
                'transaction_id': order.transaction_id,
                'total_amount': float(order.total_amount),
                'payment_method': order.payment_method,
                'customer_name': order.customer_name
            }
        })
        
    except Exception as e:
        logger.error(f"Payment status error: {str(e)}")
        return Response({
            'success': False,
            'message': 'خطا در دریافت وضعیت پرداخت'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
