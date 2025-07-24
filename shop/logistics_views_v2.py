# shop/logistics_views.py
"""
Mall Platform - Logistics API Views  
RESTful APIs for Iranian shipping integration
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
import logging

from .models import Store, Order
from .iranian_logistics import logistics_manager, calculate_shipping_costs, get_recommended_shipping, validate_iranian_address

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_shipping(request):
    """Calculate shipping costs for order"""
    try:
        from_city = request.data.get('from_city')
        to_city = request.data.get('to_city') 
        weight = float(request.data.get('weight', 1.0))
        service_preference = request.data.get('preference', 'cost')  # cost, speed, balanced
        
        if not from_city or not to_city:
            return Response({
                'success': False,
                'message': 'شهر مبدا و مقصد الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get all shipping options
        options = calculate_shipping_costs(from_city, to_city, weight)
        
        if not options:
            return Response({
                'success': False, 
                'message': 'هیچ گزینه حمل و نقل موجود نیست'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get recommended option
        recommended = get_recommended_shipping(from_city, to_city, weight, service_preference)
        
        return Response({
            'success': True,
            'options': options,
            'recommended': recommended,
            'total_options': len(options)
        })
        
    except Exception as e:
        logger.error(f"Calculate shipping error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در محاسبه هزینه حمل و نقل'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated]) 
def validate_address(request):
    """Validate Iranian address format"""
    try:
        address_data = {
            'province': request.data.get('province'),
            'city': request.data.get('city'),
            'address': request.data.get('address'),
            'postal_code': request.data.get('postal_code')
        }
        
        validation_result = validate_iranian_address(address_data)
        
        return Response({
            'success': True,
            'valid': validation_result['valid'],
            'errors': validation_result['errors']
        })
        
    except Exception as e:
        logger.error(f"Address validation error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در اعتبارسنجی آدرس'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_shipment(request, order_id):
    """Create shipment for order"""
    try:
        order = get_object_or_404(Order, id=order_id)
        
        # Check if user owns the order or store
        if order.customer != request.user and order.store.owner != request.user:
            return Response({
                'success': False,
                'message': 'دسترسی غیرمجاز'
            }, status=status.HTTP_403_FORBIDDEN)
        
        provider = request.data.get('provider', 'post')
        service_type = request.data.get('service_type', 'standard')
        
        # Prepare shipment data
        shipment_data = {
            'order_id': order.id,
            'sender': {
                'name': order.store.owner.get_full_name(),
                'phone': getattr(order.store, 'phone', ''),
                'address': getattr(order.store, 'address', ''),
                'city': getattr(order.store, 'city', 'تهران'),
                'postal_code': getattr(order.store, 'postal_code', '')
            },
            'receiver': {
                'name': order.customer.get_full_name(),
                'phone': getattr(order.customer, 'mobile', ''),
                'address': order.shipping_address,
                'city': getattr(order, 'shipping_city', ''),
                'postal_code': getattr(order, 'shipping_postal_code', '')
            },
            'package': {
                'weight': order.total_weight if hasattr(order, 'total_weight') else 1.0,
                'value': float(order.total_amount),
                'description': f'سفارش شماره {order.order_number}'
            },
            'service_type': service_type
        }
        
        # Create shipment
        result = logistics_manager.create_shipment(provider, shipment_data)
        
        if result['success']:
            # Update order with tracking info
            order.shipping_provider = provider
            order.tracking_number = result.get('tracking_number')
            order.status = 'shipped'
            order.save()
            
            return Response({
                'success': True,
                'tracking_number': result.get('tracking_number'),
                'estimated_delivery': result.get('estimated_delivery'),
                'message': 'مرسوله ایجاد شد'
            })
        else:
            return Response({
                'success': False,
                'message': result.get('error', 'خطا در ایجاد مرسوله')
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Create shipment error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در ایجاد مرسوله'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def track_shipment(request, tracking_number):
    """Track shipment status"""
    try:
        provider = request.GET.get('provider', 'post')
        
        result = logistics_manager.track_shipment(provider, tracking_number)
        
        if result['success']:
            return Response({
                'success': True,
                'tracking_info': result
            })
        else:
            return Response({
                'success': False,
                'message': result.get('error', 'خطا در پیگیری مرسوله')
            }, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        logger.error(f"Track shipment error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در پیگیری مرسوله'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_cities(request):
    """Get list of supported cities"""
    try:
        from .iranian_logistics import IRANIAN_CITIES
        
        cities_list = []
        for province, cities in IRANIAN_CITIES.items():
            for city in cities:
                cities_list.append({
                    'city': city,
                    'province': province
                })
        
        return Response({
            'success': True,
            'cities': cities_list,
            'provinces': list(IRANIAN_CITIES.keys())
        })
        
    except Exception as e:
        logger.error(f"Get cities error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در دریافت لیست شهرها'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_logistics_providers(request):
    """Get available logistics providers"""
    try:
        providers_info = []
        
        for provider_name, provider in logistics_manager.providers.items():
            provider_data = {
                'name': provider_name,
                'display_name': get_provider_display_name(provider_name),
                'description': get_provider_description(provider_name),
                'features': get_provider_features(provider_name),
                'coverage': get_provider_coverage(provider_name)
            }
            providers_info.append(provider_data)
        
        return Response({
            'success': True,
            'providers': providers_info
        })
        
    except Exception as e:
        logger.error(f"Get providers error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در دریافت ارائه‌دهندگان حمل و نقل'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_provider_display_name(provider_name: str) -> str:
    """Get display name for provider"""
    names = {
        'post': 'پست ایران',
        'tipax': 'تیپاکس', 
        'snap_express': 'اسنپ اکسپرس'
    }
    return names.get(provider_name, provider_name)


def get_provider_description(provider_name: str) -> str:
    """Get description for provider"""
    descriptions = {
        'post': 'پست ایران - ارسال به تمام نقاط کشور',
        'tipax': 'تیپاکس - ارسال سریع و مطمئن',
        'snap_express': 'اسنپ اکسپرس - ارسال همان روز در شهرهای بزرگ'
    }
    return descriptions.get(provider_name, '')


def get_provider_features(provider_name: str) -> list:
    """Get features for provider"""
    features = {
        'post': ['کشوری', 'ارزان‌ترین', 'قابل اعتماد'],
        'tipax': ['سریع', 'امن', 'بیمه شده'],
        'snap_express': ['همان روز', 'پیگیری آنلاین', 'سرویس شهری']
    }
    return features.get(provider_name, [])


def get_provider_coverage(provider_name: str) -> str:
    """Get coverage info for provider"""
    coverage = {
        'post': 'تمام شهرها و روستاهای ایران',
        'tipax': 'شهرهای بزرگ و متوسط ایران', 
        'snap_express': 'تهران، اصفهان، مشهد، شیراز'
    }
    return coverage.get(provider_name, '')
