from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Sum
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .order_models import Order, OrderItem, Cart, CartItem, Customer
from .models import Store, Product
import logging

logger = logging.getLogger(__name__)

class OrderManagementViewSet(viewsets.ModelViewSet):
    """Order management for Mall platform store owners"""
    
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter orders by user's store"""
        store = self.get_user_store()
        if store:
            return Order.objects.filter(store=store).prefetch_related('items__product')
        return Order.objects.none()
    
    def get_user_store(self):
        """Get user's store"""
        return self.request.user.stores.first() if hasattr(self.request.user, 'stores') else None
    
    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Get order statistics for dashboard"""
        try:
            store = self.get_user_store()
            if not store:
                return Response({
                    'success': False,
                    'message': 'فروشگاه یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
            
            now = timezone.now()
            today = now.date()
            thirty_days_ago = now - timedelta(days=30)
            
            # Basic counts
            total_orders = Order.objects.filter(store=store).count()
            pending_orders = Order.objects.filter(store=store, status='pending').count()
            processing_orders = Order.objects.filter(
                store=store, 
                status__in=['confirmed', 'processing']
            ).count()
            completed_orders = Order.objects.filter(
                store=store, 
                status__in=['delivered']
            ).count()
            
            # Revenue calculations
            total_revenue = Order.objects.filter(
                store=store,
                payment_status='paid'
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            monthly_revenue = Order.objects.filter(
                store=store,
                payment_status='paid',
                created_at__gte=thirty_days_ago
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            daily_revenue = Order.objects.filter(
                store=store,
                payment_status='paid',
                created_at__date=today
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            stats = {
                'total_orders': total_orders,
                'pending_orders': pending_orders,
                'processing_orders': processing_orders,
                'completed_orders': completed_orders,
                'total_revenue': float(total_revenue),
                'monthly_revenue': float(monthly_revenue),
                'daily_revenue': float(daily_revenue),
                'average_order_value': float(total_revenue / total_orders) if total_orders > 0 else 0,
            }
            
            return Response({
                'success': True,
                'data': stats
            })
            
        except Exception as e:
            logger.error(f"Error getting order stats: {str(e)}")
            return Response({
                'success': False,
                'message': 'خطا در دریافت آمار سفارشات'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """Update order status"""
        try:
            order = self.get_object()
            new_status = request.data.get('status')
            admin_notes = request.data.get('admin_notes', '')
            
            if not new_status:
                return Response({
                    'success': False,
                    'message': 'وضعیت جدید الزامی است'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate status transition
            valid_statuses = ['pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled']
            if new_status not in valid_statuses:
                return Response({
                    'success': False,
                    'message': 'وضعیت نامعتبر است'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            old_status = order.status
            order.status = new_status
            if admin_notes:
                order.admin_notes = admin_notes
            order.save()
            
            # TODO: Send SMS notification to customer about status change
            # TODO: Update inventory if order is cancelled
            
            return Response({
                'success': True,
                'message': f'وضعیت سفارش از "{old_status}" به "{new_status}" تغییر یافت',
                'data': {
                    'order_id': order.id,
                    'old_status': old_status,
                    'new_status': new_status
                }
            })
            
        except Exception as e:
            logger.error(f"Error updating order status: {str(e)}")
            return Response({
                'success': False,
                'message': 'خطا در به‌روزرسانی وضعیت سفارش'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CustomerManagementViewSet(viewsets.ModelViewSet):
    """Customer management for Mall platform"""
    
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter customers by user's store"""
        store = self.get_user_store()
        if store:
            return Customer.objects.filter(store=store)
        return Customer.objects.none()
    
    def get_user_store(self):
        """Get user's store"""
        return self.request.user.stores.first() if hasattr(self.request.user, 'stores') else None
    
    @action(detail=False, methods=['get'])
    def customer_stats(self, request):
        """Get customer statistics"""
        try:
            store = self.get_user_store()
            if not store:
                return Response({
                    'success': False,
                    'message': 'فروشگاه یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
            
            total_customers = Customer.objects.filter(store=store).count()
            active_customers = Customer.objects.filter(
                store=store,
                total_orders__gt=0
            ).count()
            
            # Recent customers (last 30 days)
            thirty_days_ago = timezone.now() - timedelta(days=30)
            recent_customers = Customer.objects.filter(
                store=store,
                created_at__gte=thirty_days_ago
            ).count()
            
            # Top customers by spending
            top_customers = Customer.objects.filter(store=store).order_by('-total_spent')[:10]
            
            top_customers_data = []
            for customer in top_customers:
                top_customers_data.append({
                    'id': customer.id,
                    'name': customer.name,
                    'phone': customer.phone,
                    'total_orders': customer.total_orders,
                    'total_spent': float(customer.total_spent),
                    'last_order_date': customer.last_order_date.isoformat() if customer.last_order_date else None
                })
            
            return Response({
                'success': True,
                'data': {
                    'total_customers': total_customers,
                    'active_customers': active_customers,
                    'recent_customers': recent_customers,
                    'top_customers': top_customers_data
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting customer stats: {str(e)}")
            return Response({
                'success': False,
                'message': 'خطا در دریافت آمار مشتریان'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
