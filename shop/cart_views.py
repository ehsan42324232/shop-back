# Shopping Cart API Views
# Customer cart management functionality

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction

from .models import Store
from .mall_models import ProductInstance
from .cart_models import Cart, CartItem

def get_or_create_cart(request, store):
    """Get or create cart for user/session"""
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(
            user=request.user,
            store=store
        )
    else:
        # Use session for anonymous users
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        
        cart, created = Cart.objects.get_or_create(
            session_key=session_key,
            store=store
        )
    return cart

@api_view(['GET'])
@permission_classes([AllowAny])
def get_cart(request, store_domain):
    """Get current cart contents"""
    try:
        store = get_object_or_404(Store, domain=store_domain, is_active=True)
        cart = get_or_create_cart(request, store)
        
        items = []
        for item in cart.items.select_related('product_instance', 'product_instance__product'):
            items.append({
                'id': item.id,
                'product_instance': {
                    'id': item.product_instance.id,
                    'sku': item.product_instance.sku,
                    'name': item.product_instance.product.name,
                    'price': str(item.product_instance.price),
                    'images': item.product_instance.product.images[:1],
                    'stock_quantity': item.product_instance.stock_quantity
                },
                'quantity': item.quantity,
                'unit_price': str(item.unit_price),
                'total_price': str(item.total_price)
            })
        
        return Response({
            'cart_id': cart.id,
            'items': items,
            'total_items': cart.total_items,
            'total_price': str(cart.total_price)
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([AllowAny])
def add_to_cart(request, store_domain):
    """Add item to cart"""
    try:
        store = get_object_or_404(Store, domain=store_domain, is_active=True)
        product_instance_id = request.data.get('product_instance_id')
        quantity = int(request.data.get('quantity', 1))
        
        if quantity <= 0:
            return Response({'error': 'تعداد باید بیشتر از صفر باشد'}, status=400)
        
        product_instance = get_object_or_404(
            ProductInstance,
            id=product_instance_id,
            product__store=store,
            is_active=True
        )
        
        if quantity > product_instance.stock_quantity:
            return Response({
                'error': f'تنها {product_instance.stock_quantity} عدد موجود است'
            }, status=400)
        
        cart = get_or_create_cart(request, store)
        
        with transaction.atomic():
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product_instance=product_instance,
                defaults={'quantity': quantity}
            )
            
            if not created:
                # Update existing item
                new_quantity = cart_item.quantity + quantity
                if new_quantity > product_instance.stock_quantity:
                    return Response({
                        'error': f'حداکثر {product_instance.stock_quantity} عدد می‌توانید اضافه کنید'
                    }, status=400)
                
                cart_item.quantity = new_quantity
                cart_item.save()
        
        return Response({
            'success': True,
            'message': 'محصول به سبد خرید اضافه شد',
            'cart_total_items': cart.total_items
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['PUT'])
@permission_classes([AllowAny])
def update_cart_item(request, store_domain, item_id):
    """Update cart item quantity"""
    try:
        store = get_object_or_404(Store, domain=store_domain, is_active=True)
        cart = get_or_create_cart(request, store)
        
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
        quantity = int(request.data.get('quantity', 1))
        
        if quantity <= 0:
            cart_item.delete()
            return Response({'success': True, 'message': 'محصول از سبد حذف شد'})
        
        if quantity > cart_item.product_instance.stock_quantity:
            return Response({
                'error': f'تنها {cart_item.product_instance.stock_quantity} عدد موجود است'
            }, status=400)
        
        cart_item.quantity = quantity
        cart_item.save()
        
        return Response({
            'success': True,
            'message': 'سبد خرید به‌روزرسانی شد'
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['DELETE'])
@permission_classes([AllowAny])
def remove_from_cart(request, store_domain, item_id):
    """Remove item from cart"""
    try:
        store = get_object_or_404(Store, domain=store_domain, is_active=True)
        cart = get_or_create_cart(request, store)
        
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
        cart_item.delete()
        
        return Response({
            'success': True,
            'message': 'محصول از سبد حذف شد'
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([AllowAny])
def clear_cart(request, store_domain):
    """Clear entire cart"""
    try:
        store = get_object_or_404(Store, domain=store_domain, is_active=True)
        cart = get_or_create_cart(request, store)
        cart.clear()
        
        return Response({
            'success': True,
            'message': 'سبد خرید خالی شد'
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)