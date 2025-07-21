from django.db import models, transaction
from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import uuid

from .models import Store
from .storefront_models import Order, OrderItem, Basket, CustomerAddress
from .serializers import OrderSerializer, OrderItemSerializer
from .middleware import get_current_store
from .utils import send_sms_notification


class OrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing orders
    """
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        store = get_current_store(self.request)
        if not store:
            return Order.objects.none()

        user = self.request.user
        
        # Store owners can see all orders for their store
        if hasattr(user, 'owned_store') and user.owned_store == store:
            return Order.objects.filter(store=store).order_by('-created_at')
        
        # Customers can only see their own orders
        return Order.objects.filter(
            store=store,
            customer=user
        ).order_by('-created_at')

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """
        Update order status (store owners only)
        """
        order = self.get_object()
        store = get_current_store(request)
        
        # Check if user is store owner
        if not hasattr(request.user, 'owned_store') or request.user.owned_store != store:
            return Response(
                {'error': 'فقط صاحب فروشگاه می‌تواند وضعیت سفارش را تغییر دهد'},
                status=status.HTTP_403_FORBIDDEN
            )

        new_status = request.data.get('status')
        tracking_code = request.data.get('tracking_code', '')
        notes = request.data.get('notes', '')

        if new_status not in dict(Order.STATUS_CHOICES):
            return Response(
                {'error': 'وضعیت نامعتبر'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update order
        old_status = order.status
        order.status = new_status
        order.tracking_code = tracking_code
        order.admin_notes = notes
        order.save()

        # Send notification to customer
        self.notify_customer_status_change(order, old_status, new_status)

        # Log status change
        self.log_status_change(order, old_status, new_status, request.user)

        return Response({
            'message': 'وضعیت سفارش با موفقیت به‌روزرسانی شد',
            'order': OrderSerializer(order).data
        })

    @action(detail=True, methods=['post'])
    def cancel_order(self, request, pk=None):
        """
        Cancel an order
        """
        order = self.get_object()
        
        # Only pending orders can be cancelled
        if order.status != 'pending':
            return Response(
                {'error': 'فقط سفارش‌های در انتظار قابل لغو هستند'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Customers can cancel their own orders within 1 hour
        if order.customer == request.user:
            time_diff = timezone.now() - order.created_at
            if time_diff.total_seconds() > 3600:  # 1 hour
                return Response(
                    {'error': 'امکان لغو سفارش بعد از یک ساعت وجود ندارد'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        # Store owners can cancel anytime
        elif not (hasattr(request.user, 'owned_store') and 
                 request.user.owned_store == order.store):
            return Response(
                {'error': 'شما مجاز به لغو این سفارش نیستید'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Cancel order
        order.status = 'cancelled'
        order.cancellation_reason = request.data.get('reason', '')
        order.cancelled_at = timezone.now()
        order.save()

        # Restore product stock
        self.restore_product_stock(order)

        # Send cancellation notification
        self.notify_order_cancellation(order)

        return Response({
            'message': 'سفارش با موفقیت لغو شد',
            'order': OrderSerializer(order).data
        })

    @action(detail=True, methods=['get'])
    def tracking_info(self, request, pk=None):
        """
        Get order tracking information
        """
        order = self.get_object()
        
        # Check if user has access to this order
        if (order.customer != request.user and 
            not (hasattr(request.user, 'owned_store') and 
                 request.user.owned_store == order.store)):
            return Response(
                {'error': 'دسترسی غیرمجاز'},
                status=status.HTTP_403_FORBIDDEN
            )

        tracking_info = {
            'order_number': order.order_number,
            'status': order.get_status_display(),
            'status_code': order.status,
            'tracking_code': order.tracking_code,
            'estimated_delivery': order.estimated_delivery_date,
            'timeline': self.get_order_timeline(order)
        }

        return Response(tracking_info)

    def get_order_timeline(self, order):
        """
        Generate order status timeline
        """
        timeline = [
            {
                'status': 'ثبت سفارش',
                'date': order.created_at,
                'completed': True,
                'description': 'سفارش شما با موفقیت ثبت شد'
            }
        ]

        status_timeline = {
            'confirmed': {
                'status': 'تأیید سفارش',
                'description': 'سفارش شما تأیید شد و در حال آماده‌سازی است'
            },
            'processing': {
                'status': 'در حال پردازش',
                'description': 'سفارش شما در حال آماده‌سازی است'
            },
            'shipped': {
                'status': 'ارسال شده',
                'description': 'سفارش شما ارسال شد'
            },
            'delivered': {
                'status': 'تحویل داده شده',
                'description': 'سفارش شما با موفقیت تحویل داده شد'
            }
        }

        current_reached = False
        for status_key, info in status_timeline.items():
            completed = order.status == status_key or current_reached
            if order.status == status_key:
                current_reached = True
            
            timeline.append({
                'status': info['status'],
                'date': order.updated_at if completed else None,
                'completed': completed,
                'description': info['description']
            })

        if order.status == 'cancelled':
            timeline.append({
                'status': 'لغو شده',
                'date': order.cancelled_at,
                'completed': True,
                'description': f'سفارش لغو شد. دلیل: {order.cancellation_reason}'
            })

        return timeline

    def notify_customer_status_change(self, order, old_status, new_status):
        """
        Send notification to customer about status change
        """
        try:
            # Email notification
            if order.customer.email:
                subject = f'تغییر وضعیت سفارش {order.order_number}'
                html_message = render_to_string('emails/order_status_change.html', {
                    'order': order,
                    'old_status': old_status,
                    'new_status': new_status
                })
                send_mail(
                    subject,
                    '',
                    settings.DEFAULT_FROM_EMAIL,
                    [order.customer.email],
                    html_message=html_message
                )

            # SMS notification
            if order.customer.phone:
                message = f'وضعیت سفارش {order.order_number} به {order.get_status_display()} تغییر کرد.'
                if order.tracking_code:
                    message += f' کد پیگیری: {order.tracking_code}'
                
                send_sms_notification(order.customer.phone, message)

        except Exception as e:
            # Log error but don't fail the request
            print(f"Failed to send notification: {e}")

    def notify_order_cancellation(self, order):
        """
        Send cancellation notification
        """
        try:
            # Email notification
            if order.customer.email:
                subject = f'لغو سفارش {order.order_number}'
                html_message = render_to_string('emails/order_cancelled.html', {
                    'order': order
                })
                send_mail(
                    subject,
                    '',
                    settings.DEFAULT_FROM_EMAIL,
                    [order.customer.email],
                    html_message=html_message
                )

            # SMS notification
            if order.customer.phone:
                message = f'سفارش {order.order_number} لغو شد.'
                send_sms_notification(order.customer.phone, message)

        except Exception as e:
            print(f"Failed to send cancellation notification: {e}")

    def restore_product_stock(self, order):
        """
        Restore product stock when order is cancelled
        """
        try:
            with transaction.atomic():
                for item in order.items.all():
                    if item.product.track_stock:
                        item.product.stock_quantity += item.quantity
                        item.product.save()
        except Exception as e:
            print(f"Failed to restore stock: {e}")

    def log_status_change(self, order, old_status, new_status, user):
        """
        Log order status change for audit
        """
        # This would typically go to a separate audit log table
        # For now, we'll just print it
        print(f"Order {order.order_number} status changed from {old_status} to {new_status} by {user.username}")


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_analytics(request):
    """
    Get order analytics for store owners
    """
    store = get_current_store(request)
    if not store:
        return Response({'error': 'Store not found'}, status=404)

    # Check if user is store owner
    if not hasattr(request.user, 'owned_store') or request.user.owned_store != store:
        return Response(
            {'error': 'Only store owners can view analytics'},
            status=status.HTTP_403_FORBIDDEN
        )

    from django.db.models import Count, Sum, Avg
    from datetime import datetime, timedelta

    # Date range
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)

    orders = Order.objects.filter(
        store=store,
        created_at__gte=start_date
    )

    # Basic stats
    total_orders = orders.count()
    total_revenue = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    avg_order_value = orders.aggregate(Avg('total_amount'))['total_amount__avg'] or 0

    # Status distribution
    status_distribution = orders.values('status').annotate(
        count=Count('id')
    ).order_by('status')

    # Daily orders
    daily_orders = []
    for i in range(days):
        date = start_date + timedelta(days=i)
        day_orders = orders.filter(
            created_at__date=date.date()
        ).aggregate(
            count=Count('id'),
            revenue=Sum('total_amount')
        )
        daily_orders.append({
            'date': date.strftime('%Y-%m-%d'),
            'orders': day_orders['count'] or 0,
            'revenue': float(day_orders['revenue'] or 0)
        })

    # Top products
    top_products = OrderItem.objects.filter(
        order__store=store,
        order__created_at__gte=start_date
    ).values('product__name').annotate(
        quantity_sold=Sum('quantity'),
        revenue=Sum(models.F('quantity') * models.F('price'))
    ).order_by('-quantity_sold')[:10]

    return Response({
        'summary': {
            'total_orders': total_orders,
            'total_revenue': float(total_revenue),
            'average_order_value': float(avg_order_value),
            'period_days': days
        },
        'status_distribution': list(status_distribution),
        'daily_orders': daily_orders,
        'top_products': list(top_products)
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_update_orders(request):
    """
    Bulk update multiple orders
    """
    store = get_current_store(request)
    if not store:
        return Response({'error': 'Store not found'}, status=404)

    # Check if user is store owner
    if not hasattr(request.user, 'owned_store') or request.user.owned_store != store:
        return Response(
            {'error': 'Only store owners can bulk update orders'},
            status=status.HTTP_403_FORBIDDEN
        )

    order_ids = request.data.get('order_ids', [])
    action = request.data.get('action')
    new_status = request.data.get('status')

    if not order_ids or not action:
        return Response(
            {'error': 'order_ids and action are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    orders = Order.objects.filter(
        id__in=order_ids,
        store=store
    )

    if orders.count() != len(order_ids):
        return Response(
            {'error': 'Some orders not found'},
            status=status.HTTP_400_BAD_REQUEST
        )

    updated_count = 0
    errors = []

    with transaction.atomic():
        for order in orders:
            try:
                if action == 'update_status' and new_status:
                    if new_status in dict(Order.STATUS_CHOICES):
                        old_status = order.status
                        order.status = new_status
                        order.save()
                        
                        # Send notification
                        OrderViewSet().notify_customer_status_change(
                            order, old_status, new_status
                        )
                        updated_count += 1
                    else:
                        errors.append(f'Invalid status for order {order.order_number}')
                
                elif action == 'mark_shipped':
                    if order.status in ['confirmed', 'processing']:
                        order.status = 'shipped'
                        order.save()
                        updated_count += 1
                    else:
                        errors.append(f'Cannot ship order {order.order_number} in current status')

            except Exception as e:
                errors.append(f'Error updating order {order.order_number}: {str(e)}')

    return Response({
        'message': f'{updated_count} orders updated successfully',
        'updated_count': updated_count,
        'errors': errors
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_orders(request):
    """
    Export orders to CSV
    """
    store = get_current_store(request)
    if not store:
        return Response({'error': 'Store not found'}, status=404)

    # Check if user is store owner
    if not hasattr(request.user, 'owned_store') or request.user.owned_store != store:
        return Response(
            {'error': 'Only store owners can export orders'},
            status=status.HTTP_403_FORBIDDEN
        )

    import csv
    from django.http import HttpResponse
    from datetime import datetime

    # Get date range
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    orders = Order.objects.filter(store=store)
    
    if start_date:
        orders = orders.filter(created_at__gte=start_date)
    if end_date:
        orders = orders.filter(created_at__lte=end_date)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="orders_{datetime.now().strftime("%Y%m%d")}.csv"'
    
    # Add BOM for proper UTF-8 encoding in Excel
    response.write('\ufeff')
    
    writer = csv.writer(response)
    writer.writerow([
        'شماره سفارش',
        'مشتری',
        'وضعیت',
        'مبلغ کل',
        'تاریخ ثبت',
        'تاریخ به‌روزرسانی',
        'کد پیگیری'
    ])

    for order in orders:
        writer.writerow([
            order.order_number,
            order.customer.get_full_name() or order.customer.username,
            order.get_status_display(),
            order.total_amount,
            order.created_at.strftime('%Y-%m-%d %H:%M'),
            order.updated_at.strftime('%Y-%m-%d %H:%M'),
            order.tracking_code or '-'
        ])

    return response
