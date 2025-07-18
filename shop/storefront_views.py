from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import json

from .models import Product, Store
from .storefront_models import (
    Basket, Order, OrderItem, DeliveryZone, 
    PaymentGateway, CustomerAddress, Wishlist
)
from .serializers import (
    BasketSerializer, OrderSerializer, OrderItemSerializer,
    CustomerAddressSerializer, WishlistSerializer
)


# ==================== سبد خرید ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_basket(request):
    """
    دریافت سبد خرید کاربر
    """
    try:
        if not hasattr(request, 'store') or not request.store:
            return Response({
                'error': 'فروشگاه یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # سبد خرید کاربر برای این فروشگاه
        basket_items = Basket.objects.filter(
            user=request.user,
            product__store=request.store
        ).select_related('product')
        
        # محاسبه مجموع
        total_amount = sum(item.total_price for item in basket_items)
        total_items = sum(item.quantity for item in basket_items)
        
        # سریالایز کردن آیتم‌ها
        items_data = []
        for item in basket_items:
            items_data.append({
                'id': item.id,
                'product': {
                    'id': str(item.product.id),
                    'title': item.product.title,
                    'price': item.product.price,
                    'image': item.product.images.first().image.url if item.product.images.exists() else None,
                    'stock': item.product.stock,
                    'is_available': item.product.stock > 0 if item.product.track_inventory else True
                },
                'quantity': item.quantity,
                'price_at_add': item.price_at_add,
                'total_price': item.total_price,
                'created_at': item.created_at
            })
        
        return Response({
            'items': items_data,
            'total_amount': total_amount,
            'total_items': total_items,
            'store': {
                'id': str(request.store.id),
                'name': request.store.name,
                'currency': request.store.currency
            }
        })
        
    except Exception as e:
        return Response({
            'error': f'خطا در دریافت سبد خرید: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_to_basket(request):
    """
    افزودن محصول به سبد خرید
    """
    try:
        data = json.loads(request.body) if isinstance(request.data, str) else request.data
        
        if not hasattr(request, 'store') or not request.store:
            return Response({
                'error': 'فروشگاه یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))
        
        if not product_id:
            return Response({
                'error': 'شناسه محصول الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if quantity <= 0:
            return Response({
                'error': 'تعداد باید بیشتر از صفر باشد'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # یافتن محصول
        product = get_object_or_404(Product, id=product_id, store=request.store, is_active=True)
        
        # بررسی موجودی
        if product.track_inventory and product.stock < quantity:
            return Response({
                'error': f'موجودی کافی نیست. موجودی فعلی: {product.stock}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # افزودن یا به‌روزرسانی سبد خرید
        with transaction.atomic():
            basket_item, created = Basket.objects.get_or_create(
                user=request.user,
                product=product,
                defaults={
                    'quantity': quantity,
                    'price_at_add': product.price
                }
            )
            
            if not created:
                # به‌روزرسانی تعداد
                new_quantity = basket_item.quantity + quantity
                
                # بررسی موجودی برای تعداد جدید
                if product.track_inventory and product.stock < new_quantity:
                    return Response({
                        'error': f'موجودی کافی نیست. موجودی فعلی: {product.stock}'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                basket_item.quantity = new_quantity
                basket_item.price_at_add = product.price  # به‌روزرسانی قیمت
                basket_item.save()
        
        return Response({
            'message': 'محصول به سبد خرید اضافه شد',
            'item': {
                'id': basket_item.id,
                'product_title': product.title,
                'quantity': basket_item.quantity,
                'total_price': basket_item.total_price
            }
        })
        
    except Exception as e:
        return Response({
            'error': f'خطا در افزودن به سبد خرید: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_basket_item(request, item_id):
    """
    به‌روزرسانی تعداد آیتم سبد خرید
    """
    try:
        data = json.loads(request.body) if isinstance(request.data, str) else request.data
        quantity = int(data.get('quantity', 1))
        
        if quantity <= 0:
            return Response({
                'error': 'تعداد باید بیشتر از صفر باشد'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        basket_item = get_object_or_404(
            Basket, 
            id=item_id, 
            user=request.user,
            product__store=request.store
        )
        
        # بررسی موجودی
        if basket_item.product.track_inventory and basket_item.product.stock < quantity:
            return Response({
                'error': f'موجودی کافی نیست. موجودی فعلی: {basket_item.product.stock}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        basket_item.quantity = quantity
        basket_item.save()
        
        return Response({
            'message': 'سبد خرید به‌روزرسانی شد',
            'item': {
                'id': basket_item.id,
                'quantity': basket_item.quantity,
                'total_price': basket_item.total_price
            }
        })
        
    except Exception as e:
        return Response({
            'error': f'خطا در به‌روزرسانی سبد خرید: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_from_basket(request, item_id):
    """
    حذف آیتم از سبد خرید
    """
    try:
        basket_item = get_object_or_404(
            Basket, 
            id=item_id, 
            user=request.user,
            product__store=request.store
        )
        
        basket_item.delete()
        
        return Response({
            'message': 'آیتم از سبد خرید حذف شد'
        })
        
    except Exception as e:
        return Response({
            'error': f'خطا در حذف از سبد خرید: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_basket(request):
    """
    خالی کردن سبد خرید
    """
    try:
        Basket.objects.filter(
            user=request.user,
            product__store=request.store
        ).delete()
        
        return Response({
            'message': 'سبد خرید خالی شد'
        })
        
    except Exception as e:
        return Response({
            'error': f'خطا در خالی کردن سبد خرید: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== سفارش‌ها ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_orders(request):
    """
    دریافت سفارش‌های کاربر
    """
    try:
        if not hasattr(request, 'store') or not request.store:
            return Response({
                'error': 'فروشگاه یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        orders = Order.objects.filter(
            user=request.user,
            store=request.store
        ).order_by('-created_at')
        
        orders_data = []
        for order in orders:
            orders_data.append({
                'id': str(order.id),
                'order_number': order.order_number,
                'status': order.status,
                'payment_status': order.payment_status,
                'total_amount': order.total_amount,
                'final_amount': order.final_amount,
                'created_at': order.created_at,
                'expected_delivery_date': order.expected_delivery_date,
                'tracking_number': order.tracking_number,
                'items_count': order.items.count()
            })
        
        return Response({
            'orders': orders_data
        })
        
    except Exception as e:
        return Response({
            'error': f'خطا در دریافت سفارش‌ها: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_order_detail(request, order_id):
    """
    دریافت جزئیات سفارش
    """
    try:
        order = get_object_or_404(
            Order, 
            id=order_id, 
            user=request.user,
            store=request.store
        )
        
        # آیتم‌های سفارش
        items = []
        for item in order.items.all():
            items.append({
                'id': item.id,
                'product_title': item.product_title,
                'product_sku': item.product_sku,
                'quantity': item.quantity,
                'price_at_order': item.price_at_order,
                'total_price': item.total_price,
                'product_attributes': item.product_attributes
            })
        
        return Response({
            'order': {
                'id': str(order.id),
                'order_number': order.order_number,
                'status': order.status,
                'payment_status': order.payment_status,
                'total_amount': order.total_amount,
                'tax_amount': order.tax_amount,
                'shipping_amount': order.shipping_amount,
                'discount_amount': order.discount_amount,
                'final_amount': order.final_amount,
                'payment_method': order.payment_method,
                'delivery_method': order.delivery_method,
                'expected_delivery_date': order.expected_delivery_date,
                'tracking_number': order.tracking_number,
                'shipping_address': order.shipping_address,
                'customer_name': order.customer_name,
                'customer_phone': order.customer_phone,
                'customer_notes': order.customer_notes,
                'created_at': order.created_at,
                'items': items
            }
        })
        
    except Exception as e:
        return Response({
            'error': f'خطا در دریافت جزئیات سفارش: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_order(request):
    """
    ایجاد سفارش از سبد خرید
    """
    try:
        data = json.loads(request.body) if isinstance(request.data, str) else request.data
        
        if not hasattr(request, 'store') or not request.store:
            return Response({
                'error': 'فروشگاه یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # بررسی سبد خرید
        basket_items = Basket.objects.filter(
            user=request.user,
            product__store=request.store
        ).select_related('product')
        
        if not basket_items.exists():
            return Response({
                'error': 'سبد خرید خالی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # اطلاعات سفارش
        delivery_method = data.get('delivery_method', 'standard')
        shipping_address = data.get('shipping_address', {})
        customer_name = data.get('customer_name', f'{request.user.first_name} {request.user.last_name}')
        customer_phone = data.get('customer_phone', '')
        customer_notes = data.get('customer_notes', '')
        
        # محاسبه مبالغ
        total_amount = sum(item.total_price for item in basket_items)
        tax_amount = total_amount * request.store.tax_rate
        shipping_amount = Decimal(data.get('shipping_amount', '0'))
        discount_amount = Decimal(data.get('discount_amount', '0'))
        
        with transaction.atomic():
            # بررسی موجودی محصولات
            for item in basket_items:
                if item.product.track_inventory and item.product.stock < item.quantity:
                    return Response({
                        'error': f'موجودی کافی نیست برای {item.product.title}'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # ایجاد سفارش
            order = Order.objects.create(
                user=request.user,
                store=request.store,
                total_amount=total_amount,
                tax_amount=tax_amount,
                shipping_amount=shipping_amount,
                discount_amount=discount_amount,
                delivery_method=delivery_method,
                shipping_address=shipping_address,
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_notes=customer_notes
            )
            
            # ایجاد آیتم‌های سفارش و کم کردن موجودی
            for item in basket_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price_at_order=item.price_at_add
                )
                
                # کم کردن موجودی
                if item.product.track_inventory:
                    item.product.stock -= item.quantity
                    item.product.save()
            
            # پاک کردن سبد خرید
            basket_items.delete()
        
        return Response({
            'message': 'سفارش با موفقیت ثبت شد',
            'order': {
                'id': str(order.id),
                'order_number': order.order_number,
                'final_amount': order.final_amount,
                'status': order.status
            }
        })
        
    except Exception as e:
        return Response({
            'error': f'خطا در ثبت سفارش: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== آدرس‌ها ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_addresses(request):
    """
    دریافت آدرس‌های کاربر
    """
    try:
        addresses = CustomerAddress.objects.filter(user=request.user)
        
        addresses_data = []
        for address in addresses:
            addresses_data.append({
                'id': address.id,
                'title': address.title,
                'recipient_name': address.recipient_name,
                'phone': address.phone,
                'province': address.province,
                'city': address.city,
                'address': address.address,
                'postal_code': address.postal_code,
                'is_default': address.is_default
            })
        
        return Response({
            'addresses': addresses_data
        })
        
    except Exception as e:
        return Response({
            'error': f'خطا در دریافت آدرس‌ها: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_address(request):
    """
    ایجاد آدرس جدید
    """
    try:
        data = json.loads(request.body) if isinstance(request.data, str) else request.data
        
        required_fields = ['title', 'recipient_name', 'phone', 'province', 'city', 'address', 'postal_code']
        
        for field in required_fields:
            if not data.get(field):
                return Response({
                    'error': f'فیلد {field} الزامی است'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # اگر آدرس پیش‌فرض انتخاب شده، سایر آدرس‌ها را غیرپیش‌فرض کن
        is_default = data.get('is_default', False)
        if is_default:
            CustomerAddress.objects.filter(user=request.user).update(is_default=False)
        
        address = CustomerAddress.objects.create(
            user=request.user,
            title=data['title'],
            recipient_name=data['recipient_name'],
            phone=data['phone'],
            province=data['province'],
            city=data['city'],
            address=data['address'],
            postal_code=data['postal_code'],
            is_default=is_default
        )
        
        return Response({
            'message': 'آدرس با موفقیت ثبت شد',
            'address': {
                'id': address.id,
                'title': address.title,
                'recipient_name': address.recipient_name,
                'phone': address.phone,
                'province': address.province,
                'city': address.city,
                'address': address.address,
                'postal_code': address.postal_code,
                'is_default': address.is_default
            }
        })
        
    except Exception as e:
        return Response({
            'error': f'خطا در ثبت آدرس: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_address(request, address_id):
    """
    به‌روزرسانی آدرس
    """
    try:
        data = json.loads(request.body) if isinstance(request.data, str) else request.data
        
        address = get_object_or_404(CustomerAddress, id=address_id, user=request.user)
        
        # فیلدهای قابل به‌روزرسانی
        updateable_fields = ['title', 'recipient_name', 'phone', 'province', 'city', 'address', 'postal_code']
        
        for field in updateable_fields:
            if field in data:
                setattr(address, field, data[field])
        
        # مدیریت آدرس پیش‌فرض
        if 'is_default' in data and data['is_default']:
            CustomerAddress.objects.filter(user=request.user).update(is_default=False)
            address.is_default = True
        
        address.save()
        
        return Response({
            'message': 'آدرس با موفقیت به‌روزرسانی شد'
        })
        
    except Exception as e:
        return Response({
            'error': f'خطا در به‌روزرسانی آدرس: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_address(request, address_id):
    """
    حذف آدرس
    """
    try:
        address = get_object_or_404(CustomerAddress, id=address_id, user=request.user)
        address.delete()
        
        return Response({
            'message': 'آدرس با موفقیت حذف شد'
        })
        
    except Exception as e:
        return Response({
            'error': f'خطا در حذف آدرس: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== لیست علاقه‌مندی ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_wishlist(request):
    """
    دریافت لیست علاقه‌مندی کاربر
    """
    try:
        if not hasattr(request, 'store') or not request.store:
            return Response({
                'error': 'فروشگاه یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        wishlist_items = Wishlist.objects.filter(
            user=request.user,
            product__store=request.store
        ).select_related('product')
        
        items_data = []
        for item in wishlist_items:
            items_data.append({
                'id': item.id,
                'product': {
                    'id': str(item.product.id),
                    'title': item.product.title,
                    'price': item.product.price,
                    'image': item.product.images.first().image.url if item.product.images.exists() else None,
                    'is_available': item.product.stock > 0 if item.product.track_inventory else True
                },
                'created_at': item.created_at
            })
        
        return Response({
            'wishlist': items_data
        })
        
    except Exception as e:
        return Response({
            'error': f'خطا در دریافت لیست علاقه‌مندی: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_to_wishlist(request):
    """
    افزودن محصول به لیست علاقه‌مندی
    """
    try:
        data = json.loads(request.body) if isinstance(request.data, str) else request.data
        
        if not hasattr(request, 'store') or not request.store:
            return Response({
                'error': 'فروشگاه یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        product_id = data.get('product_id')
        
        if not product_id:
            return Response({
                'error': 'شناسه محصول الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        product = get_object_or_404(Product, id=product_id, store=request.store, is_active=True)
        
        # افزودن به لیست علاقه‌مندی
        wishlist_item, created = Wishlist.objects.get_or_create(
            user=request.user,
            product=product
        )
        
        if created:
            return Response({
                'message': 'محصول به لیست علاقه‌مندی اضافه شد'
            })
        else:
            return Response({
                'message': 'محصول قبلاً در لیست علاقه‌مندی موجود است'
            })
        
    except Exception as e:
        return Response({
            'error': f'خطا در افزودن به لیست علاقه‌مندی: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_from_wishlist(request, item_id):
    """
    حذف محصول از لیست علاقه‌مندی
    """
    try:
        wishlist_item = get_object_or_404(
            Wishlist, 
            id=item_id, 
            user=request.user,
            product__store=request.store
        )
        
        wishlist_item.delete()
        
        return Response({
            'message': 'محصول از لیست علاقه‌مندی حذف شد'
        })
        
    except Exception as e:
        return Response({
            'error': f'خطا در حذف از لیست علاقه‌مندی: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== اطلاعات تحویل ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_delivery_info(request):
    """
    دریافت اطلاعات تحویل فروشگاه
    """
    try:
        if not hasattr(request, 'store') or not request.store:
            return Response({
                'error': 'فروشگاه یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        delivery_zones = DeliveryZone.objects.filter(
            store=request.store,
            is_active=True
        )
        
        zones_data = []
        for zone in delivery_zones:
            zones_data.append({
                'id': zone.id,
                'name': zone.name,
                'description': zone.description,
                'standard_price': zone.standard_price,
                'express_price': zone.express_price,
                'same_day_price': zone.same_day_price,
                'standard_days': zone.standard_days,
                'express_days': zone.express_days,
                'same_day_available': zone.same_day_available,
                'free_delivery_threshold': zone.free_delivery_threshold
            })
        
        return Response({
            'delivery_zones': zones_data
        })
        
    except Exception as e:
        return Response({
            'error': f'خطا در دریافت اطلاعات تحویل: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
