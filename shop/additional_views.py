from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Avg
from django.http import HttpResponse
from django.conf import settings
import csv
import json
from datetime import datetime
from .models import Product
from .storefront_models import DeliveryZone
from .serializers import ProductListSerializer
from .middleware import get_current_store
from .utils import generate_sample_import_template, get_store_analytics


class ProductSearchView(APIView):
    """
    Advanced product search with filters
    """
    def get(self, request):
        store = get_current_store(request)
        if not store:
            return Response({'error': 'فروشگاهی یافت نشد'}, status=status.HTTP_404_NOT_FOUND)
        
        queryset = Product.objects.filter(store=store, is_active=True)
        
        # Search query
        search_query = request.GET.get('q', '')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(sku__icontains=search_query)
            )
        
        # Category filter
        category_id = request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Price range filter
        min_price = request.GET.get('min_price')
        max_price = request.GET.get('max_price')
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
        
        # Availability filter
        in_stock = request.GET.get('in_stock')
        if in_stock == 'true':
            queryset = queryset.filter(Q(track_inventory=False) | Q(stock__gt=0))
        
        # Featured filter
        featured = request.GET.get('featured')
        if featured == 'true':
            queryset = queryset.filter(is_featured=True)
        
        # Attribute filters
        for key, value in request.GET.items():
            if key.startswith('attr_'):
                attr_slug = key.replace('attr_', '')
                queryset = queryset.filter(
                    attribute_values__attribute__slug=attr_slug,
                    attribute_values__value__icontains=value
                )
        
        # Sorting
        sort_by = request.GET.get('sort', 'created_at')
        sort_order = request.GET.get('order', 'desc')
        
        valid_sort_fields = ['title', 'price', 'created_at', 'stock']
        if sort_by in valid_sort_fields:
            if sort_order == 'desc':
                sort_by = f'-{sort_by}'
            queryset = queryset.order_by(sort_by)
        
        # Pagination
        page_size = min(int(request.GET.get('page_size', 20)), 100)
        page = int(request.GET.get('page', 1))
        
        start = (page - 1) * page_size
        end = start + page_size
        
        total_count = queryset.count()
        products = queryset[start:end]
        
        serializer = ProductListSerializer(products, many=True, context={'request': request})
        
        return Response({
            'results': serializer.data,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size
        })


class DeliveryCalculatorView(APIView):
    """
    Calculate delivery cost and time
    """
    def post(self, request):
        store = get_current_store(request)
        if not store:
            return Response({'error': 'فروشگاهی یافت نشد'}, status=status.HTTP_404_NOT_FOUND)
        
        zone_id = request.data.get('zone_id')
        delivery_method = request.data.get('delivery_method', 'standard')
        total_amount = request.data.get('total_amount', 0)
        
        try:
            zone = DeliveryZone.objects.get(id=zone_id, store=store, is_active=True)
        except DeliveryZone.DoesNotExist:
            return Response({'error': 'منطقه تحویل یافت نشد'}, status=status.HTTP_404_NOT_FOUND)
        
        # Calculate delivery cost
        delivery_cost = 0
        delivery_days = 0
        
        if delivery_method == 'standard':
            delivery_cost = zone.standard_price
            delivery_days = zone.standard_days
        elif delivery_method == 'express':
            delivery_cost = zone.express_price
            delivery_days = zone.express_days
        elif delivery_method == 'same_day' and zone.same_day_available:
            delivery_cost = zone.same_day_price
            delivery_days = 0
        else:
            return Response({'error': 'روش تحویل نامعتبر'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check for free delivery
        if total_amount >= zone.free_delivery_threshold and zone.free_delivery_threshold > 0:
            delivery_cost = 0
        
        return Response({
            'delivery_cost': delivery_cost,
            'delivery_days': delivery_days,
            'is_free': delivery_cost == 0,
            'zone_name': zone.name
        })


class PaymentProcessView(APIView):
    """
    Process payment for orders
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        store = get_current_store(request)
        if not store:
            return Response({'error': 'فروشگاهی یافت نشد'}, status=status.HTTP_404_NOT_FOUND)
        
        order_id = request.data.get('order_id')
        payment_method = request.data.get('payment_method')
        
        try:
            from .storefront_models import Order
            order = Order.objects.get(id=order_id, user=request.user, store=store)
        except Order.DoesNotExist:
            return Response({'error': 'سفارش یافت نشد'}, status=status.HTTP_404_NOT_FOUND)
        
        if order.payment_status == 'paid':
            return Response({'error': 'سفارش قبلاً پرداخت شده'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get payment gateway settings
        try:
            from .storefront_models import PaymentGateway
            gateway = PaymentGateway.objects.get(
                store=store,
                gateway_type=payment_method,
                is_active=True
            )
        except PaymentGateway.DoesNotExist:
            return Response({'error': 'درگاه پرداخت یافت نشد'}, status=status.HTTP_404_NOT_FOUND)
        
        # Here you would integrate with the actual payment gateway
        # For now, we'll simulate a successful payment
        
        # Update order payment status
        order.payment_method = payment_method
        order.payment_status = 'paid'
        order.payment_id = f"PAY_{order.order_number}_{payment_method}"
        order.save()
        
        return Response({
            'message': 'پرداخت با موفقیت انجام شد',
            'payment_id': order.payment_id,
            'order_number': order.order_number
        })


class ProductExportView(APIView):
    """
    Export products to CSV for store owners
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        store = get_current_store(request)
        if not store or store.owner != request.user:
            return Response({'error': 'غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
        
        # Get products to export
        products = Product.objects.filter(store=store).select_related('category').prefetch_related('attribute_values__attribute')
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="products_{store.slug}.csv"'
        
        # Add BOM for UTF-8
        response.write('\ufeff')
        
        writer = csv.writer(response)
        
        # Write header
        header = [
            'title', 'category_level_1', 'category_level_2', 'category_level_3',
            'price', 'compare_price', 'stock', 'sku', 'description',
            'attribute_1_name', 'attribute_1_value',
            'attribute_2_name', 'attribute_2_value',
            'attribute_3_name', 'attribute_3_value'
        ]
        writer.writerow(header)
        
        # Write data
        for product in products:
            row = [
                product.title,
                '',  # category_level_1
                '',  # category_level_2
                '',  # category_level_3
                product.price,
                product.compare_price or '',
                product.stock,
                product.sku or '',
                product.description or '',
                '',  # attribute_1_name
                '',  # attribute_1_value
                '',  # attribute_2_name
                '',  # attribute_2_value
                '',  # attribute_3_name
                '',  # attribute_3_value
            ]
            
            # Add category hierarchy
            if product.category:
                category_path = product.category.get_full_path().split(' > ')
                for i, level in enumerate(category_path[:3]):
                    row[i + 1] = level
            
            # Add attributes
            attributes = list(product.attribute_values.all()[:3])
            for i, attr_value in enumerate(attributes):
                row[9 + i * 2] = attr_value.attribute.name
                row[10 + i * 2] = attr_value.value
            
            writer.writerow(row)
        
        return response


class ImportTemplateView(APIView):
    """
    Download CSV import template
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        store = get_current_store(request)
        if not store or store.owner != request.user:
            return Response({'error': 'غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
        
        # Generate sample template
        df = generate_sample_import_template()
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="import_template.csv"'
        
        # Add BOM for UTF-8
        response.write('\ufeff')
        
        # Write CSV
        df.to_csv(response, index=False, encoding='utf-8')
        
        return response


class StoreAnalyticsView(APIView):
    """
    Get store analytics data
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        store = get_current_store(request)
        if not store or store.owner != request.user:
            return Response({'error': 'غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
        
        # Get date range from query params
        from datetime import datetime, timedelta
        
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        if date_from:
            date_from = datetime.strptime(date_from, '%Y-%m-%d')
        else:
            date_from = datetime.now() - timedelta(days=30)
        
        if date_to:
            date_to = datetime.strptime(date_to, '%Y-%m-%d')
        else:
            date_to = datetime.now()
        
        analytics = get_store_analytics(store, date_from, date_to)
        return Response(analytics)


class StoreConfigView(APIView):
    """
    Get store configuration for frontend
    """
    def get(self, request):
        store = get_current_store(request)
        if not store:
            return Response({'error': 'فروشگاهی یافت نشد'}, status=status.HTTP_404_NOT_FOUND)
        
        from .storefront_models import DeliveryZone, PaymentGateway
        
        # Get delivery zones
        delivery_zones = DeliveryZone.objects.filter(store=store, is_active=True)
        
        # Get payment gateways
        payment_gateways = PaymentGateway.objects.filter(store=store, is_active=True)
        
        config = {
            'store': {
                'id': store.id,
                'name': store.name,
                'description': store.description,
                'currency': store.currency,
                'logo': store.logo.url if store.logo else None,
                'email': store.email,
                'phone': store.phone,
                'address': store.address,
            },
            'delivery_zones': [
                {
                    'id': zone.id,
                    'name': zone.name,
                    'standard_price': zone.standard_price,
                    'express_price': zone.express_price,
                    'same_day_price': zone.same_day_price,
                    'standard_days': zone.standard_days,
                    'express_days': zone.express_days,
                    'same_day_available': zone.same_day_available,
                    'free_delivery_threshold': zone.free_delivery_threshold,
                }
                for zone in delivery_zones
            ],
            'payment_gateways': [
                {
                    'type': gateway.gateway_type,
                    'display_name': gateway.get_gateway_type_display(),
                }
                for gateway in payment_gateways
            ]
        }
        
        return Response(config)


class HealthCheckView(APIView):
    """
    Health check endpoint
    """
    def get(self, request):
        store = get_current_store(request)
        
        return Response({
            'status': 'healthy',
            'store': store.name if store else None,
            'timestamp': datetime.now().isoformat()
        })
