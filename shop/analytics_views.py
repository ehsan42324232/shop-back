from django.http import JsonResponse
from django.db.models import Count, Sum, Avg, Q, F
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone
from datetime import datetime, timedelta
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import models

from .models import Store, Product, Category
from .storefront_models import Order, OrderItem
from .chat_models import ChatSession, SupportAgent
from .sms_models import SMSCampaign, SMSMessage


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_store_analytics(request):
    """Get comprehensive analytics for store owner"""
    try:
        # Get user's store
        store = Store.objects.filter(owner=request.user).first()
        if not store:
            return Response({'error': 'فروشگاهی یافت نشد'}, status=404)
        
        # Date ranges
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        year_ago = today - timedelta(days=365)
        
        # Basic counts
        total_products = store.products.filter(is_active=True).count()
        total_categories = store.categories.filter(is_active=True).count()
        total_orders = store.orders.count()
        total_customers = store.orders.values('user').distinct().count()
        
        # Revenue analytics
        total_revenue = store.orders.filter(
            payment_status='paid'
        ).aggregate(total=Sum('final_amount'))['total'] or 0
        
        monthly_revenue = store.orders.filter(
            payment_status='paid',
            created_at__date__gte=month_ago
        ).aggregate(total=Sum('final_amount'))['total'] or 0
        
        weekly_revenue = store.orders.filter(
            payment_status='paid',
            created_at__date__gte=week_ago
        ).aggregate(total=Sum('final_amount'))['total'] or 0
        
        daily_revenue = store.orders.filter(
            payment_status='paid',
            created_at__date=today
        ).aggregate(total=Sum('final_amount'))['total'] or 0
        
        # Order analytics
        pending_orders = store.orders.filter(status='pending').count()
        processing_orders = store.orders.filter(status='processing').count()
        shipped_orders = store.orders.filter(status='shipped').count()
        delivered_orders = store.orders.filter(status='delivered').count()
        
        # Product analytics
        low_stock_products = store.products.filter(
            track_inventory=True,
            stock__lte=F('low_stock_threshold')
        ).count()
        
        out_of_stock_products = store.products.filter(
            track_inventory=True,
            stock=0
        ).count()
        
        # Top selling products
        top_products = OrderItem.objects.filter(
            order__store=store,
            order__payment_status='paid'
        ).values(
            'product__title', 'product__id'
        ).annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum(F('quantity') * F('price_at_order'))
        ).order_by('-total_sold')[:10]
        
        # Daily sales chart data (last 30 days)
        daily_sales = store.orders.filter(
            payment_status='paid',
            created_at__date__gte=month_ago
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            sales=Sum('final_amount'),
            orders=Count('id')
        ).order_by('date')
        
        # Monthly sales chart data (last 12 months)
        monthly_sales = store.orders.filter(
            payment_status='paid',
            created_at__date__gte=year_ago
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            sales=Sum('final_amount'),
            orders=Count('id')
        ).order_by('month')
        
        # Customer analytics
        new_customers_this_month = store.orders.filter(
            created_at__date__gte=month_ago
        ).values('user').annotate(
            first_order=models.Min('created_at')
        ).filter(
            first_order__date__gte=month_ago
        ).count()
        
        repeat_customers = store.orders.values('user').annotate(
            order_count=Count('id')
        ).filter(order_count__gt=1).count()
        
        # Average order value
        avg_order_value = store.orders.filter(
            payment_status='paid'
        ).aggregate(avg=Avg('final_amount'))['avg'] or 0
        
        analytics_data = {
            'overview': {
                'total_products': total_products,
                'total_categories': total_categories,
                'total_orders': total_orders,
                'total_customers': total_customers,
                'low_stock_products': low_stock_products,
                'out_of_stock_products': out_of_stock_products
            },
            'revenue': {
                'total': float(total_revenue),
                'monthly': float(monthly_revenue),
                'weekly': float(weekly_revenue),
                'daily': float(daily_revenue),
                'average_order_value': float(avg_order_value)
            },
            'orders': {
                'pending': pending_orders,
                'processing': processing_orders,
                'shipped': shipped_orders,
                'delivered': delivered_orders,
                'total': total_orders
            },
            'customers': {
                'total': total_customers,
                'new_this_month': new_customers_this_month,
                'repeat_customers': repeat_customers,
                'repeat_rate': round((repeat_customers / total_customers * 100), 2) if total_customers > 0 else 0
            },
            'top_products': [
                {
                    'id': item['product__id'],
                    'title': item['product__title'],
                    'quantity_sold': item['total_sold'],
                    'revenue': float(item['total_revenue'])
                }
                for item in top_products
            ],
            'charts': {
                'daily_sales': [
                    {
                        'date': item['date'].isoformat(),
                        'sales': float(item['sales']),
                        'orders': item['orders']
                    }
                    for item in daily_sales
                ],
                'monthly_sales': [
                    {
                        'month': item['month'].strftime('%Y-%m'),
                        'sales': float(item['sales']),
                        'orders': item['orders']
                    }
                    for item in monthly_sales
                ]
            }
        }
        
        return Response(analytics_data)
        
    except Exception as e:
        return Response({'error': 'خطا در دریافت آمار'}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_product_analytics(request, product_id):
    """Get analytics for a specific product"""
    try:
        store = Store.objects.filter(owner=request.user).first()
        if not store:
            return Response({'error': 'فروشگاهی یافت نشد'}, status=404)
        
        product = store.products.filter(id=product_id).first()
        if not product:
            return Response({'error': 'محصولی یافت نشد'}, status=404)
        
        # Date ranges
        today = timezone.now().date()
        month_ago = today - timedelta(days=30)
        
        # Basic stats
        total_sold = OrderItem.objects.filter(
            product=product,
            order__payment_status='paid'
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        total_revenue = OrderItem.objects.filter(
            product=product,
            order__payment_status='paid'
        ).aggregate(
            total=Sum(F('quantity') * F('price_at_order'))
        )['total'] or 0
        
        # Monthly performance
        monthly_sold = OrderItem.objects.filter(
            product=product,
            order__payment_status='paid',
            order__created_at__date__gte=month_ago
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        monthly_revenue = OrderItem.objects.filter(
            product=product,
            order__payment_status='paid',
            order__created_at__date__gte=month_ago
        ).aggregate(
            total=Sum(F('quantity') * F('price_at_order'))
        )['total'] or 0
        
        # Stock analytics
        stock_status = 'in_stock'
        if product.track_inventory:
            if product.stock == 0:
                stock_status = 'out_of_stock'
            elif product.stock <= product.low_stock_threshold:
                stock_status = 'low_stock'
        
        analytics_data = {
            'product': {
                'id': product.id,
                'title': product.title,
                'price': float(product.price),
                'stock': product.stock,
                'stock_status': stock_status
            },
            'sales': {
                'total_quantity': total_sold,
                'total_revenue': float(total_revenue),
                'monthly_quantity': monthly_sold,
                'monthly_revenue': float(monthly_revenue)
            },
            'inventory': {
                'current_stock': product.stock,
                'low_stock_threshold': product.low_stock_threshold,
                'track_inventory': product.track_inventory
            }
        }
        
        return Response(analytics_data)
        
    except Exception as e:
        return Response({'error': 'خطا در دریافت آمار محصول'}, status=500)


@api_view(['GET'])
def get_platform_analytics(request):
    """Get platform-wide analytics (admin only)"""
    try:
        if not request.user.is_staff:
            return Response({'error': 'شما مجاز نیستید'}, status=403)
        
        # Date ranges
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Store analytics
        total_stores = Store.objects.count()
        active_stores = Store.objects.filter(is_active=True).count()
        approved_stores = Store.objects.filter(is_approved=True).count()
        pending_stores = Store.objects.filter(is_approved=False).count()
        
        new_stores_this_month = Store.objects.filter(
            created_at__date__gte=month_ago
        ).count()
        
        # Product analytics
        total_products = Product.objects.count()
        active_products = Product.objects.filter(is_active=True).count()
        
        # Order analytics
        total_orders = Order.objects.count()
        total_revenue = Order.objects.filter(
            payment_status='paid'
        ).aggregate(total=Sum('final_amount'))['total'] or 0
        
        monthly_orders = Order.objects.filter(
            created_at__date__gte=month_ago
        ).count()
        
        monthly_revenue = Order.objects.filter(
            payment_status='paid',
            created_at__date__gte=month_ago
        ).aggregate(total=Sum('final_amount'))['total'] or 0
        
        # Top performing stores
        top_stores = Store.objects.annotate(
            total_revenue=Sum('orders__final_amount', filter=Q(orders__payment_status='paid')),
            total_orders=Count('orders', filter=Q(orders__payment_status='paid'))
        ).order_by('-total_revenue')[:10]
        
        # Platform growth
        daily_signups = Store.objects.filter(
            created_at__date__gte=month_ago
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            signups=Count('id')
        ).order_by('date')
        
        analytics_data = {
            'stores': {
                'total': total_stores,
                'active': active_stores,
                'approved': approved_stores,
                'pending': pending_stores,
                'new_this_month': new_stores_this_month
            },
            'products': {
                'total': total_products,
                'active': active_products
            },
            'orders': {
                'total': total_orders,
                'monthly': monthly_orders
            },
            'revenue': {
                'total': float(total_revenue),
                'monthly': float(monthly_revenue)
            },
            'top_stores': [
                {
                    'id': store.id,
                    'name': store.name,
                    'revenue': float(store.total_revenue or 0),
                    'orders': store.total_orders
                }
                for store in top_stores
            ],
            'growth': {
                'daily_signups': [
                    {
                        'date': item['date'].isoformat(),
                        'signups': item['signups']
                    }
                    for item in daily_signups
                ]
            }
        }
        
        return Response(analytics_data)
        
    except Exception as e:
        return Response({'error': 'خطا در دریافت آمار پلتفرم'}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_sales_report(request):
    """Get detailed sales report"""
    try:
        store = Store.objects.filter(owner=request.user).first()
        if not store:
            return Response({'error': 'فروشگاهی یافت نشد'}, status=404)
        
        # Get date range from query params
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start_date = timezone.now().date() - timedelta(days=30)
            
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end_date = timezone.now().date()
        
        # Filter orders
        orders = store.orders.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        # Sales summary
        total_orders = orders.count()
        paid_orders = orders.filter(payment_status='paid').count()
        total_revenue = orders.filter(payment_status='paid').aggregate(
            total=Sum('final_amount')
        )['total'] or 0
        
        # Daily breakdown
        daily_breakdown = orders.filter(payment_status='paid').annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            orders=Count('id'),
            revenue=Sum('final_amount')
        ).order_by('date')
        
        # Product breakdown
        product_breakdown = OrderItem.objects.filter(
            order__store=store,
            order__payment_status='paid',
            order__created_at__date__gte=start_date,
            order__created_at__date__lte=end_date
        ).values(
            'product__title', 'product__id'
        ).annotate(
            quantity=Sum('quantity'),
            revenue=Sum(F('quantity') * F('price_at_order'))
        ).order_by('-revenue')
        
        # Category breakdown
        category_breakdown = OrderItem.objects.filter(
            order__store=store,
            order__payment_status='paid',
            order__created_at__date__gte=start_date,
            order__created_at__date__lte=end_date
        ).values(
            'product__category__name'
        ).annotate(
            quantity=Sum('quantity'),
            revenue=Sum(F('quantity') * F('price_at_order'))
        ).order_by('-revenue')
        
        report_data = {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': {
                'total_orders': total_orders,
                'paid_orders': paid_orders,
                'total_revenue': float(total_revenue),
                'conversion_rate': round((paid_orders / total_orders * 100), 2) if total_orders > 0 else 0,
                'average_order_value': float(total_revenue / paid_orders) if paid_orders > 0 else 0
            },
            'daily_breakdown': [
                {
                    'date': item['date'].isoformat(),
                    'orders': item['orders'],
                    'revenue': float(item['revenue'])
                }
                for item in daily_breakdown
            ],
            'product_breakdown': [
                {
                    'product_id': item['product__id'],
                    'product_name': item['product__title'],
                    'quantity': item['quantity'],
                    'revenue': float(item['revenue'])
                }
                for item in product_breakdown[:20]  # Top 20 products
            ],
            'category_breakdown': [
                {
                    'category_name': item['product__category__name'] or 'بدون دسته‌بندی',
                    'quantity': item['quantity'],
                    'revenue': float(item['revenue'])
                }
                for item in category_breakdown
            ]
        }
        
        return Response(report_data)
        
    except Exception as e:
        return Response({'error': 'خطا در تهیه گزارش فروش'}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_inventory_report(request):
    """Get inventory status report"""
    try:
        store = Store.objects.filter(owner=request.user).first()
        if not store:
            return Response({'error': 'فروشگاهی یافت نشد'}, status=404)
        
        # Inventory analytics
        total_products = store.products.filter(is_active=True).count()
        
        # Stock status
        in_stock = store.products.filter(
            is_active=True,
            track_inventory=True,
            stock__gt=F('low_stock_threshold')
        ).count()
        
        low_stock = store.products.filter(
            is_active=True,
            track_inventory=True,
            stock__lte=F('low_stock_threshold'),
            stock__gt=0
        ).count()
        
        out_of_stock = store.products.filter(
            is_active=True,
            track_inventory=True,
            stock=0
        ).count()
        
        not_tracked = store.products.filter(
            is_active=True,
            track_inventory=False
        ).count()
        
        # Low stock products
        low_stock_products = store.products.filter(
            is_active=True,
            track_inventory=True,
            stock__lte=F('low_stock_threshold')
        ).values(
            'id', 'title', 'stock', 'low_stock_threshold', 'sku'
        ).order_by('stock')
        
        # Top selling products (to prioritize restocking)
        top_selling = OrderItem.objects.filter(
            order__store=store,
            order__payment_status='paid',
            order__created_at__date__gte=timezone.now().date() - timedelta(days=30)
        ).values(
            'product__id', 'product__title', 'product__stock'
        ).annotate(
            quantity_sold=Sum('quantity')
        ).order_by('-quantity_sold')[:10]
        
        report_data = {
            'summary': {
                'total_products': total_products,
                'in_stock': in_stock,
                'low_stock': low_stock,
                'out_of_stock': out_of_stock,
                'not_tracked': not_tracked
            },
            'stock_distribution': [
                {'status': 'موجود', 'count': in_stock},
                {'status': 'کم موجود', 'count': low_stock},
                {'status': 'ناموجود', 'count': out_of_stock},
                {'status': 'ردیابی نمی‌شود', 'count': not_tracked}
            ],
            'low_stock_products': [
                {
                    'id': item['id'],
                    'title': item['title'],
                    'stock': item['stock'],
                    'threshold': item['low_stock_threshold'],
                    'sku': item['sku']
                }
                for item in low_stock_products
            ],
            'top_selling_products': [
                {
                    'id': item['product__id'],
                    'title': item['product__title'],
                    'current_stock': item['product__stock'],
                    'sold_last_month': item['quantity_sold']
                }
                for item in top_selling
            ]
        }
        
        return Response(report_data)
        
    except Exception as e:
        return Response({'error': 'خطا در تهیه گزارش موجودی'}, status=500)
