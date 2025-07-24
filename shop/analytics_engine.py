from django.db.models import Count, Sum, Avg, Q, F
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json

from .models import Product, Order, OrderItem, ProductInstance
from .customer_models import CustomerProfile, WalletTransaction, CustomerNotification
from .storefront_models import ProductView, SearchQuery


class AnalyticsEngine:
    """
    Comprehensive analytics engine for Mall platform
    Provides detailed insights for Iranian e-commerce metrics
    """
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes cache
        self._cache = {}
    
    def get_dashboard_overview(self, store_id: int = None, days: int = 30) -> dict:
        """
        Get comprehensive dashboard overview with Persian formatting
        """
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Base queryset filters
        order_filter = {'created_at__gte': start_date, 'created_at__lte': end_date}
        
        if store_id:
            order_filter['store_id'] = store_id
        
        # Revenue metrics
        total_revenue = Order.objects.filter(
            status='DELIVERED',
            **order_filter
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Order metrics
        total_orders = Order.objects.filter(**order_filter).count()
        completed_orders = Order.objects.filter(status='DELIVERED', **order_filter).count()
        pending_orders = Order.objects.filter(status__in=['PENDING', 'CONFIRMED'], **order_filter).count()
        
        # Customer metrics
        new_customers = CustomerProfile.objects.filter(
            registration_date__gte=start_date,
            registration_date__lte=end_date
        ).count()
        
        active_customers = Order.objects.filter(
            **order_filter
        ).values('customer').distinct().count()
        
        # Product metrics
        total_products = Product.objects.filter(is_active=True).count()
        if store_id:
            total_products = Product.objects.filter(is_active=True, store_id=store_id).count()
        
        low_stock_products = ProductInstance.objects.filter(
            stock_quantity__lt=10,
            stock_quantity__gt=0
        ).count()
        
        out_of_stock_products = ProductInstance.objects.filter(
            stock_quantity=0
        ).count()
        
        # Calculate growth rates
        previous_period_start = start_date - timedelta(days=days)
        previous_period_end = start_date
        
        previous_revenue = Order.objects.filter(
            status='DELIVERED',
            created_at__gte=previous_period_start,
            created_at__lte=previous_period_end
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        revenue_growth = self._calculate_growth_rate(previous_revenue, total_revenue)
        
        previous_orders = Order.objects.filter(
            created_at__gte=previous_period_start,
            created_at__lte=previous_period_end
        ).count()
        
        orders_growth = self._calculate_growth_rate(previous_orders, total_orders)
        
        return {
            'overview': {
                'total_revenue': {
                    'value': float(total_revenue),
                    'formatted': self._format_persian_currency(total_revenue),
                    'growth_rate': revenue_growth,
                    'growth_formatted': f"{revenue_growth:+.1f}%"
                },
                'total_orders': {
                    'value': total_orders,
                    'formatted': f"{total_orders:,}",
                    'growth_rate': orders_growth,
                    'growth_formatted': f"{orders_growth:+.1f}%"
                },
                'completed_orders': {
                    'value': completed_orders,
                    'formatted': f"{completed_orders:,}",
                    'completion_rate': (completed_orders / total_orders * 100) if total_orders > 0 else 0
                },
                'pending_orders': {
                    'value': pending_orders,
                    'formatted': f"{pending_orders:,}"
                },
                'new_customers': {
                    'value': new_customers,
                    'formatted': f"{new_customers:,}"
                },
                'active_customers': {
                    'value': active_customers,
                    'formatted': f"{active_customers:,}"
                },
                'average_order_value': {
                    'value': float(total_revenue / total_orders) if total_orders > 0 else 0,
                    'formatted': self._format_persian_currency(total_revenue / total_orders if total_orders > 0 else 0)
                }
            },
            'inventory': {
                'total_products': total_products,
                'low_stock_products': low_stock_products,
                'out_of_stock_products': out_of_stock_products,
                'stock_health_score': self._calculate_stock_health_score(total_products, low_stock_products, out_of_stock_products)
            },
            'period': {
                'days': days,
                'start_date': start_date.strftime('%Y/%m/%d'),
                'end_date': end_date.strftime('%Y/%m/%d'),
                'persian_start': self._format_persian_date(start_date),
                'persian_end': self._format_persian_date(end_date)
            }
        }
    
    def get_real_time_metrics(self, store_id: int = None) -> dict:
        """
        Get real-time metrics for live dashboard
        """
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Today's metrics
        today_orders = Order.objects.filter(
            created_at__gte=today_start
        )
        
        if store_id:
            today_orders = today_orders.filter(store_id=store_id)
        
        today_revenue = today_orders.filter(
            status='DELIVERED'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        # Current hour metrics
        current_hour_start = now.replace(minute=0, second=0, microsecond=0)
        current_hour_orders = today_orders.filter(
            created_at__gte=current_hour_start
        ).count()
        
        # Online customers (active in last 5 minutes)
        online_customers = ProductView.objects.filter(
            created_at__gte=now - timedelta(minutes=5)
        ).values('user').distinct().count()
        
        # Recent activities
        recent_orders = Order.objects.filter(
            created_at__gte=now - timedelta(hours=24)
        ).order_by('-created_at')[:10]
        
        if store_id:
            recent_orders = recent_orders.filter(store_id=store_id)
        
        return {
            'real_time': {
                'current_timestamp': now.isoformat(),
                'persian_time': self._format_persian_datetime(now),
                'today_revenue': {
                    'value': float(today_revenue),
                    'formatted': self._format_persian_currency(today_revenue)
                },
                'today_orders': today_orders.count(),
                'current_hour_orders': current_hour_orders,
                'online_customers': online_customers
            },
            'recent_activities': [
                {
                    'order_id': order.order_number,
                    'customer_name': order.customer.get_full_name() or 'مشتری',
                    'amount': float(order.total_amount),
                    'amount_formatted': self._format_persian_currency(order.total_amount),
                    'status': order.get_status_display(),
                    'time_ago': self._time_ago_persian(order.created_at)
                }
                for order in recent_orders
            ]
        }
    
    # Helper methods
    def _calculate_growth_rate(self, previous_value: float, current_value: float) -> float:
        """Calculate growth rate percentage"""
        if previous_value == 0:
            return 100.0 if current_value > 0 else 0.0
        return ((current_value - previous_value) / previous_value) * 100
    
    def _calculate_stock_health_score(self, total: int, low_stock: int, out_of_stock: int) -> float:
        """Calculate overall stock health score (0-100)"""
        if total == 0:
            return 100.0
        
        healthy_products = total - low_stock - out_of_stock
        return (healthy_products / total) * 100
    
    def _format_persian_currency(self, amount: float) -> str:
        """Format currency in Persian style"""
        try:
            return f"{amount:,.0f} تومان".replace(',', '٬')
        except:
            return "0 تومان"
    
    def _format_persian_date(self, date: datetime) -> str:
        """Format date in Persian calendar"""
        try:
            # Simple Persian date formatting (you can use jdatetime for accurate conversion)
            return date.strftime('%Y/%m/%d')
        except:
            return ""
    
    def _format_persian_datetime(self, dt: datetime) -> str:
        """Format datetime in Persian"""
        try:
            return dt.strftime('%Y/%m/%d %H:%M')
        except:
            return ""
    
    def _time_ago_persian(self, dt: datetime) -> str:
        """Calculate time ago in Persian"""
        now = timezone.now()
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days} روز پیش"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} ساعت پیش"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} دقیقه پیش"
        else:
            return "همین الان"
    
    def get_export_data(self, data_type: str, store_id: int = None, start_date: str = None, end_date: str = None) -> dict:
        """
        Export analytics data in various formats
        """
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        else:
            start_date = timezone.now() - timedelta(days=30)
        
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        else:
            end_date = timezone.now()
        
        if data_type == 'sales':
            return self._export_sales_data(store_id, start_date, end_date)
        elif data_type == 'customers':
            return self._export_customer_data(store_id, start_date, end_date)
        elif data_type == 'products':
            return self._export_product_data(store_id, start_date, end_date)
        else:
            return {'error': 'نوع داده نامعتبر است'}
    
    def _export_sales_data(self, store_id: int, start_date: datetime, end_date: datetime) -> dict:
        """Export detailed sales data"""
        orders = Order.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date,
            status='DELIVERED'
        )
        
        if store_id:
            orders = orders.filter(store_id=store_id)
        
        sales_data = []
        for order in orders:
            sales_data.append({
                'order_number': order.order_number,
                'date': order.created_at.strftime('%Y/%m/%d'),
                'customer_name': order.customer.get_full_name() or 'نامشخص',
                'total_amount': float(order.total_amount),
                'payment_method': order.payment_method,
                'items_count': order.items.count(),
                'status': order.get_status_display()
            })
        
        return {
            'data': sales_data,
            'total_records': len(sales_data),
            'period': f"{start_date.strftime('%Y/%m/%d')} تا {end_date.strftime('%Y/%m/%d')}"
        }
    
    def _export_customer_data(self, store_id: int, start_date: datetime, end_date: datetime) -> dict:
        """Export customer data"""
        customers = CustomerProfile.objects.filter(
            registration_date__gte=start_date,
            registration_date__lte=end_date
        )
        
        customer_data = []
        for customer in customers:
            customer_data.append({
                'customer_id': customer.id,
                'name': customer.user.get_full_name() or 'نامشخص',
                'phone': customer.phone,
                'registration_date': customer.registration_date.strftime('%Y/%m/%d'),
                'total_orders': customer.total_orders,
                'total_spent': float(customer.total_spent),
                'status': customer.get_status_display_persian(),
                'city': customer.city or 'نامشخص'
            })
        
        return {
            'data': customer_data,
            'total_records': len(customer_data),
            'period': f"{start_date.strftime('%Y/%m/%d')} تا {end_date.strftime('%Y/%m/%d')}"
        }
    
    def _export_product_data(self, store_id: int, start_date: datetime, end_date: datetime) -> dict:
        """Export product performance data"""
        products = Product.objects.filter(is_active=True)
        if store_id:
            products = products.filter(store_id=store_id)
        
        product_data = []
        for product in products:
            # Calculate sales in the given period
            sales_data = OrderItem.objects.filter(
                product=product,
                order__status='DELIVERED',
                order__created_at__gte=start_date,
                order__created_at__lte=end_date
            ).aggregate(
                total_quantity=Sum('quantity'),
                total_revenue=Sum(F('quantity') * F('price'))
            )
            
            product_data.append({
                'product_id': product.id,
                'name': product.name,
                'category': product.category.name if hasattr(product, 'category') and product.category else 'بدون دسته‌بندی',
                'price': float(product.price),
                'quantity_sold': sales_data['total_quantity'] or 0,
                'revenue': float(sales_data['total_revenue'] or 0),
                'stock_quantity': sum([instance.stock_quantity for instance in product.instances.all()]),
                'created_date': product.created_at.strftime('%Y/%m/%d') if hasattr(product, 'created_at') else 'نامشخص'
            })
        
        return {
            'data': product_data,
            'total_records': len(product_data),
            'period': f"{start_date.strftime('%Y/%m/%d')} تا {end_date.strftime('%Y/%m/%d')}"
        }


# Global analytics engine instance
analytics_engine = AnalyticsEngine()
