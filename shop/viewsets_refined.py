"""
Refined ViewSets with enhanced functionality and optimizations
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.db.models import Q, Count, Sum, Avg
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.cache import cache

from .models import Store, Product, Category, ProductImage
from .storefront_models import Basket, Order, OrderItem, CustomerAddress
from .serializers_refined import (
    UserProfileSerializer, StoreProfileSerializer, ProductListSerializer,
    ProductDetailSerializer, CategoryTreeSerializer, BasketItemSerializer,
    OrderSerializer, OrderCreateSerializer, CustomerAddressSerializer,
    DashboardStatsSerializer
)


class UserProfileViewSet(viewsets.ModelViewSet):
    """Enhanced user profile management"""
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return User.objects.filter(id=self.request.user.id)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Change user password"""
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        
        if not user.check_password(old_password):
            return Response(
                {'error': 'Invalid old password'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(new_password)
        user.save()
        
        return Response({'message': 'Password changed successfully'})


class StoreManagementViewSet(viewsets.ModelViewSet):
    """Store management for owners"""
    serializer_class = StoreProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Store.objects.filter(owner=self.request.user)
    
    @action(detail=True, methods=['get'])
    def dashboard_stats(self, request, pk=None):
        """Get dashboard statistics"""
        store = self.get_object()
        
        # Calculate stats
        total_products = store.products.count()
        orders = Order.objects.filter(items__product__store=store).distinct()
        total_orders = orders.count()
        total_revenue = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        pending_orders = orders.filter(status='pending').count()
        low_stock_products = store.products.filter(stock__lt=10).count()
        
        # Recent orders
        recent_orders = orders.order_by('-created_at')[:10]
        
        # Top products
        top_products = store.products.annotate(
            order_count=Count('orderitem')
        ).order_by('-order_count')[:10]
        
        stats = {
            'total_products': total_products,
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'pending_orders': pending_orders,
            'low_stock_products': low_stock_products,
            'recent_orders': OrderSerializer(recent_orders, many=True).data,
            'top_products': ProductListSerializer(top_products, many=True, context={'request': request}).data
        }
        
        serializer = DashboardStatsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get detailed analytics"""
        store = self.get_object()
        
        # Sales analytics
        orders = Order.objects.filter(items__product__store=store)
        
        # Monthly sales
        from django.db.models import TruncMonth
        monthly_sales = orders.annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            total=Sum('total_amount'),
            count=Count('id')
        ).order_by('month')
        
        # Category performance
        category_stats = store.products.values('category__name').annotate(
            product_count=Count('id'),
            avg_price=Avg('price'),
            total_stock=Sum('stock')
        )
        
        return Response({
            'monthly_sales': list(monthly_sales),
            'category_stats': list(category_stats)
        })


class OptimizedProductViewSet(viewsets.ModelViewSet):
    """Optimized product management with caching"""
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and hasattr(user, 'owned_stores'):
            # Store owners see their products
            return Product.objects.filter(store__owner=user).select_related(
                'category', 'store'
            ).prefetch_related('images')
        else:
            # Public view - active products only
            return Product.objects.filter(is_active=True).select_related(
                'category', 'store'
            ).prefetch_related('images')
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductListSerializer
    
    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    def list(self, request, *args, **kwargs):
        """Cached product list"""
        return super().list(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured products"""
        cache_key = 'featured_products'
        featured = cache.get(cache_key)
        
        if featured is None:
            featured = Product.objects.filter(
                is_active=True,
                stock__gt=0
            ).order_by('-created_at')[:12]
            cache.set(cache_key, featured, 60 * 30)  # Cache for 30 minutes
        
        serializer = ProductListSerializer(featured, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Advanced product search"""
        query = request.query_params.get('q', '')
        category = request.query_params.get('category')
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        in_stock = request.query_params.get('in_stock')
        
        products = self.get_queryset()
        
        if query:
            products = products.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(sku__icontains=query)
            )
        
        if category:
            products = products.filter(category__slug=category)
        
        if min_price:
            products = products.filter(price__gte=min_price)
        
        if max_price:
            products = products.filter(price__lte=max_price)
        
        if in_stock == 'true':
            products = products.filter(stock__gt=0)
        
        # Paginate results
        page = self.paginate_queryset(products)
        if page is not None:
            serializer = ProductListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = ProductListSerializer(products, many=True, context={'request': request})
        return Response(serializer.data)


class CategoryManagementViewSet(viewsets.ModelViewSet):
    """Enhanced category management"""
    serializer_class = CategoryTreeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and hasattr(user, 'owned_stores'):
            # Store owners see their categories
            return Category.objects.filter(store__owner=user).prefetch_related('children')
        else:
            # Public view - active categories only
            return Category.objects.filter(is_active=True).prefetch_related('children')
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get category tree structure"""
        categories = self.get_queryset().filter(parent=None)
        serializer = self.get_serializer(categories, many=True)
        return Response(serializer.data)


class ShoppingCartViewSet(viewsets.ModelViewSet):
    """Enhanced shopping cart management"""
    serializer_class = BasketItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Basket.objects.filter(user=self.request.user).select_related('product')
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get cart summary"""
        items = self.get_queryset()
        total_items = sum(item.quantity for item in items)
        total_price = sum(item.quantity * item.product.price for item in items)
        
        return Response({
            'total_items': total_items,
            'total_price': total_price,
            'items': BasketItemSerializer(items, many=True, context={'request': request}).data
        })
    
    @action(detail=False, methods=['post'])
    def add_item(self, request):
        """Add item to cart"""
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 1))
        
        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        if product.stock < quantity:
            return Response(
                {'error': 'Insufficient stock'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        basket_item, created = Basket.objects.get_or_create(
            user=request.user,
            product=product,
            defaults={'quantity': quantity}
        )
        
        if not created:
            basket_item.quantity += quantity
            basket_item.save()
        
        serializer = BasketItemSerializer(basket_item, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def update_quantity(self, request, pk=None):
        """Update item quantity"""
        basket_item = self.get_object()
        quantity = int(request.data.get('quantity', 1))
        
        if quantity <= 0:
            basket_item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        
        if basket_item.product.stock < quantity:
            return Response(
                {'error': 'Insufficient stock'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        basket_item.quantity = quantity
        basket_item.save()
        
        serializer = BasketItemSerializer(basket_item, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def clear(self, request):
        """Clear all cart items"""
        self.get_queryset().delete()
        return Response({'message': 'Cart cleared successfully'})


class OrderManagementViewSet(viewsets.ModelViewSet):
    """Enhanced order management"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'owned_stores'):
            # Store owners see orders for their products
            return Order.objects.filter(
                items__product__store__owner=user
            ).distinct().select_related('customer').prefetch_related('items')
        else:
            # Customers see their own orders
            return Order.objects.filter(customer=user).select_related(
                'delivery_address'
            ).prefetch_related('items')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderSerializer
    
    def perform_create(self, serializer):
        serializer.save(customer=self.request.user)
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update order status (store owners only)"""
        order = self.get_object()
        new_status = request.data.get('status')
        
        # Check if user is store owner
        if not hasattr(request.user, 'owned_stores'):
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        valid_statuses = ['pending', 'processing', 'shipped', 'delivered', 'cancelled']
        if new_status not in valid_statuses:
            return Response(
                {'error': 'Invalid status'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = new_status
        order.save()
        
        serializer = OrderSerializer(order, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_orders(self, request):
        """Get customer's orders"""
        orders = Order.objects.filter(customer=request.user).order_by('-created_at')
        
        page = self.paginate_queryset(orders)
        if page is not None:
            serializer = OrderSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = OrderSerializer(orders, many=True, context={'request': request})
        return Response(serializer.data)


class CustomerAddressViewSet(viewsets.ModelViewSet):
    """Customer address management"""
    serializer_class = CustomerAddressSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return CustomerAddress.objects.filter(customer=self.request.user)
    
    def perform_create(self, serializer):
        # If this is set as default, unset other defaults
        if serializer.validated_data.get('is_default'):
            CustomerAddress.objects.filter(
                customer=self.request.user,
                is_default=True
            ).update(is_default=False)
        
        serializer.save(customer=self.request.user)
    
    def perform_update(self, serializer):
        # If this is set as default, unset other defaults
        if serializer.validated_data.get('is_default'):
            CustomerAddress.objects.filter(
                customer=self.request.user,
                is_default=True
            ).exclude(id=self.get_object().id).update(is_default=False)
        
        serializer.save()
    
    @action(detail=False, methods=['get'])
    def default(self, request):
        """Get default address"""
        try:
            address = CustomerAddress.objects.get(
                customer=request.user,
                is_default=True
            )
            serializer = CustomerAddressSerializer(address)
            return Response(serializer.data)
        except CustomerAddress.DoesNotExist:
            return Response(
                {'error': 'No default address found'}, 
                status=status.HTTP_404_NOT_FOUND
            )


class ReportsViewSet(viewsets.ViewSet):
    """Business reports and analytics"""
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def sales_report(self, request):
        """Generate sales report"""
        # Check if user is store owner
        if not hasattr(request.user, 'owned_stores'):
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        store = request.user.owned_stores.first()
        if not store:
            return Response(
                {'error': 'No store found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        # Get date range from query params
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)  # Default to last 30 days
        
        if request.query_params.get('start_date'):
            start_date = datetime.strptime(
                request.query_params.get('start_date'), 
                '%Y-%m-%d'
            )
        
        if request.query_params.get('end_date'):
            end_date = datetime.strptime(
                request.query_params.get('end_date'), 
                '%Y-%m-%d'
            )
        
        # Get orders in date range
        orders = Order.objects.filter(
            items__product__store=store,
            created_at__range=[start_date, end_date]
        ).distinct()
        
        # Calculate metrics
        total_sales = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        total_orders = orders.count()
        avg_order_value = total_sales / total_orders if total_orders > 0 else 0
        
        # Top selling products
        from django.db.models import F
        top_products = OrderItem.objects.filter(
            order__in=orders
        ).values('product__title').annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum(F('quantity') * F('price'))
        ).order_by('-total_quantity')[:10]
        
        return Response({
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            },
            'metrics': {
                'total_sales': total_sales,
                'total_orders': total_orders,
                'avg_order_value': avg_order_value
            },
            'top_products': list(top_products)
        })
    
    @action(detail=False, methods=['get'])
    def inventory_report(self, request):
        """Generate inventory report"""
        # Check if user is store owner
        if not hasattr(request.user, 'owned_stores'):
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        store = request.user.owned_stores.first()
        if not store:
            return Response(
                {'error': 'No store found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get inventory stats
        products = store.products.all()
        total_products = products.count()
        in_stock = products.filter(stock__gt=0).count()
        out_of_stock = products.filter(stock=0).count()
        low_stock = products.filter(stock__lt=10, stock__gt=0).count()
        
        # Get low stock products
        low_stock_products = products.filter(
            stock__lt=10, 
            stock__gt=0
        ).values('title', 'stock', 'price')
        
        return Response({
            'summary': {
                'total_products': total_products,
                'in_stock': in_stock,
                'out_of_stock': out_of_stock,
                'low_stock': low_stock
            },
            'low_stock_products': list(low_stock_products)
        })
