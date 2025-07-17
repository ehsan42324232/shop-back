from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q, Count, Avg, F
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
import pandas as pd
import json
from datetime import datetime
import os

from .models import (
    Store, Category, Product, ProductAttribute, ProductAttributeValue,
    ProductImage, Comment, Rating, BulkImportLog
)
from .storefront_models import (
    Basket, Order, OrderItem, DeliveryZone, PaymentGateway,
    CustomerAddress, Wishlist
)
from .serializers import (
    StoreSerializer, StoreCreateSerializer, CategorySerializer,
    ProductListSerializer, ProductDetailSerializer, ProductCreateUpdateSerializer,
    ProductAttributeSerializer, CommentSerializer, RatingSerializer,
    BulkImportLogSerializer, BulkImportSerializer,
    BasketSerializer, OrderListSerializer, OrderDetailSerializer,
    OrderCreateSerializer, DeliveryZoneSerializer, PaymentGatewaySerializer,
    CustomerAddressSerializer, WishlistSerializer
)
from .middleware import get_current_store
from .utils import process_bulk_import


class IsStoreOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow store owners to edit their stores.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions for any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only to the owner of the store
        if hasattr(obj, 'store'):
            return obj.store.owner == request.user
        elif hasattr(obj, 'owner'):
            return obj.owner == request.user
        
        return False


class IsStoreOwner(permissions.BasePermission):
    """
    Permission to only allow store owners to access their store data.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        store = get_current_store(request)
        if not store:
            return False
        
        return store.owner == request.user


# Platform Management ViewSets (for platform admin)
class PlatformStoreViewSet(viewsets.ModelViewSet):
    """
    Platform admin viewset for managing all stores
    """
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'is_approved', 'currency']
    search_fields = ['name', 'name_en', 'domain', 'owner__username', 'owner__email']
    ordering_fields = ['created_at', 'name', 'requested_at', 'approved_at']
    ordering = ['-created_at']

    def get_permissions(self):
        """
        Only superusers can access platform management
        """
        if not self.request.user.is_superuser:
            self.permission_denied(self.request, message="فقط مدیران پلتفرم اجازه دسترسی دارند")
        return super().get_permissions()

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a store"""
        store = self.get_object()
        store.is_approved = True
        store.approved_at = datetime.now()
        store.save()
        return Response({'message': 'فروشگاه تایید شد'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a store"""
        store = self.get_object()
        store.is_approved = False
        store.is_active = False
        store.save()
        return Response({'message': 'فروشگاه رد شد'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def pending_requests(self, request):
        """Get pending store requests"""
        pending_stores = Store.objects.filter(is_approved=False, is_active=True)
        page = self.paginate_queryset(pending_stores)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(pending_stores, many=True)
        return Response(serializer.data)


# Store Owner ViewSets
class StoreRequestViewSet(viewsets.ModelViewSet):
    """
    Store owners can request new stores
    """
    serializer_class = StoreCreateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Store.objects.filter(owner=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        store = serializer.save()
        
        return Response({
            'message': 'درخواست فروشگاه با موفقیت ثبت شد. منتظر تایید مدیر پلتفرم باشید.',
            'store_id': store.id
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Check store approval status"""
        store = self.get_object()
        return Response({
            'is_approved': store.is_approved,
            'is_active': store.is_active,
            'requested_at': store.requested_at,
            'approved_at': store.approved_at
        })


class StoreManagementViewSet(viewsets.ModelViewSet):
    """
    Store owners manage their approved stores
    """
    serializer_class = StoreSerializer
    permission_classes = [IsStoreOwner]

    def get_queryset(self):
        store = get_current_store(self.request)
        if store:
            return Store.objects.filter(id=store.id)
        return Store.objects.none()

    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Get store dashboard statistics"""
        store = get_current_store(request)
        if not store:
            return Response({'error': 'فروشگاهی یافت نشد'}, status=status.HTTP_404_NOT_FOUND)
        
        stats = {
            'products_count': store.products.filter(is_active=True).count(),
            'categories_count': store.categories.filter(is_active=True).count(),
            'orders_count': store.orders.count(),
            'pending_orders': store.orders.filter(status='pending').count(),
            'low_stock_products': store.products.filter(
                track_inventory=True,
                stock__lte=F('low_stock_threshold')
            ).count(),
            'recent_orders': list(store.orders.order_by('-created_at')[:5].values(
                'id', 'order_number', 'status', 'total_amount', 'created_at'
            ))
        }
        return Response(stats)


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsStoreOwnerOrReadOnly]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'sort_order', 'created_at']
    ordering = ['sort_order', 'name']

    def get_queryset(self):
        store = get_current_store(self.request)
        if store:
            return Category.objects.filter(store=store, is_active=True)
        return Category.objects.none()

    def perform_create(self, serializer):
        store = get_current_store(self.request)
        serializer.save(store=store)

    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get category tree structure"""
        categories = self.get_queryset().filter(parent=None)
        serializer = self.get_serializer(categories, many=True)
        return Response(serializer.data)


class ProductAttributeViewSet(viewsets.ModelViewSet):
    serializer_class = ProductAttributeSerializer
    permission_classes = [IsStoreOwner]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name', 'sort_order', 'created_at']
    ordering = ['sort_order', 'name']

    def get_queryset(self):
        store = get_current_store(self.request)
        if store:
            return ProductAttribute.objects.filter(store=store)
        return ProductAttribute.objects.none()

    def perform_create(self, serializer):
        store = get_current_store(self.request)
        serializer.save(store=store)


class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStoreOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'is_active', 'is_featured', 'is_digital']
    search_fields = ['title', 'description', 'sku']
    ordering_fields = ['title', 'price', 'stock', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        store = get_current_store(self.request)
        if store:
            queryset = Product.objects.filter(store=store)
            
            # For non-owners, only show active products
            if not (self.request.user.is_authenticated and store.owner == self.request.user):
                queryset = queryset.filter(is_active=True)
            
            return queryset
        return Product.objects.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ProductCreateUpdateSerializer
        return ProductDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['store'] = get_current_store(self.request)
        return context

    def perform_create(self, serializer):
        store = get_current_store(self.request)
        serializer.save(store=store)

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured products"""
        products = self.get_queryset().filter(is_featured=True, is_active=True)
        page = self.paginate_queryset(products)
        if page is not None:
            serializer = ProductListSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)
        
        serializer = ProductListSerializer(products, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Get low stock products for store owners"""
        if not (request.user.is_authenticated and 
                get_current_store(request) and 
                get_current_store(request).owner == request.user):
            return Response({'error': 'غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
        
        products = self.get_queryset().filter(
            track_inventory=True,
            stock__lte=F('low_stock_threshold')
        )
        serializer = ProductListSerializer(products, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def bulk_import(self, request):
        """Bulk import products from CSV/Excel"""
        if not (request.user.is_authenticated and 
                get_current_store(request) and 
                get_current_store(request).owner == request.user):
            return Response({'error': 'غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = BulkImportSerializer(data=request.data)
        if serializer.is_valid():
            store = get_current_store(request)
            result = process_bulk_import(serializer.validated_data['file'], store, request.user)
            return Response(result, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def add_to_wishlist(self, request, pk=None):
        """Add product to wishlist"""
        if not request.user.is_authenticated:
            return Response({'error': 'ابتدا وارد شوید'}, status=status.HTTP_401_UNAUTHORIZED)
        
        product = self.get_object()
        wishlist_item, created = Wishlist.objects.get_or_create(
            user=request.user,
            product=product
        )
        
        if created:
            return Response({'message': 'محصول به لیست علاقه‌مندی اضافه شد'})
        else:
            return Response({'message': 'محصول قبلاً در لیست علاقه‌مندی موجود است'})


# Storefront ViewSets (for customers)
class BasketViewSet(viewsets.ModelViewSet):
    serializer_class = BasketSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        store = get_current_store(self.request)
        if store:
            return Basket.objects.filter(
                user=self.request.user,
                product__store=store
            )
        return Basket.objects.none()

    def perform_create(self, serializer):
        # Check if item already exists, update quantity instead
        product = serializer.validated_data['product']
        quantity = serializer.validated_data['quantity']
        
        existing_item = Basket.objects.filter(
            user=self.request.user,
            product=product
        ).first()
        
        if existing_item:
            existing_item.quantity += quantity
            existing_item.save()
            return existing_item
        else:
            return serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get basket summary"""
        items = self.get_queryset()
        total_items = sum(item.quantity for item in items)
        total_price = sum(item.total_price for item in items)
        
        return Response({
            'total_items': total_items,
            'total_price': total_price,
            'items_count': items.count()
        })

    @action(detail=False, methods=['post'])
    def clear(self, request):
        """Clear all items from basket"""
        self.get_queryset().delete()
        return Response({'message': 'سبد خرید پاک شد'})


class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'payment_status']
    ordering_fields = ['created_at', 'total_amount']
    ordering = ['-created_at']

    def get_queryset(self):
        store = get_current_store(self.request)
        if store:
            # Store owners see all orders for their store
            if store.owner == self.request.user:
                return Order.objects.filter(store=store)
            # Customers see only their orders
            else:
                return Order.objects.filter(user=self.request.user, store=store)
        return Order.objects.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return OrderListSerializer
        elif self.action == 'create':
            return OrderCreateSerializer
        return OrderDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['store'] = get_current_store(self.request)
        return context

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update order status (store owners only)"""
        order = self.get_object()
        store = get_current_store(request)
        
        if not (store and store.owner == request.user):
            return Response({'error': 'غیرمجاز'}, status=status.HTTP_403_FORBIDDEN)
        
        new_status = request.data.get('status')
        if new_status in dict(Order.STATUS_CHOICES):
            order.status = new_status
            
            # Update timestamps based on status
            if new_status == 'confirmed' and not order.confirmed_at:
                order.confirmed_at = datetime.now()
            elif new_status == 'shipped' and not order.shipped_at:
                order.shipped_at = datetime.now()
            elif new_status == 'delivered' and not order.delivered_at:
                order.delivered_at = datetime.now()
            
            order.save()
            return Response({'message': 'وضعیت سفارش به‌روزرسانی شد'})
        
        return Response({'error': 'وضعیت نامعتبر'}, status=status.HTTP_400_BAD_REQUEST)


class DeliveryZoneViewSet(viewsets.ModelViewSet):
    serializer_class = DeliveryZoneSerializer
    permission_classes = [IsStoreOwner]

    def get_queryset(self):
        store = get_current_store(self.request)
        if store:
            return DeliveryZone.objects.filter(store=store)
        return DeliveryZone.objects.none()

    def perform_create(self, serializer):
        store = get_current_store(self.request)
        serializer.save(store=store)


class PaymentGatewayViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentGatewaySerializer
    permission_classes = [IsStoreOwner]

    def get_queryset(self):
        store = get_current_store(self.request)
        if store:
            return PaymentGateway.objects.filter(store=store)
        return PaymentGateway.objects.none()

    def perform_create(self, serializer):
        store = get_current_store(self.request)
        serializer.save(store=store)


class CustomerAddressViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerAddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CustomerAddress.objects.filter(user=self.request.user)


class WishlistViewSet(viewsets.ModelViewSet):
    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        store = get_current_store(self.request)
        if store:
            return Wishlist.objects.filter(
                user=self.request.user,
                product__store=store
            )
        return Wishlist.objects.none()

    @action(detail=False, methods=['post'])
    def add_to_basket(self, request):
        """Add wishlist items to basket"""
        product_ids = request.data.get('product_ids', [])
        if not product_ids:
            return Response({'error': 'هیچ محصولی انتخاب نشده'}, status=status.HTTP_400_BAD_REQUEST)
        
        wishlist_items = self.get_queryset().filter(product_id__in=product_ids)
        added_count = 0
        
        for item in wishlist_items:
            basket_item, created = Basket.objects.get_or_create(
                user=request.user,
                product=item.product,
                defaults={'quantity': 1}
            )
            if not created:
                basket_item.quantity += 1
                basket_item.save()
            added_count += 1
        
        return Response({
            'message': f'{added_count} محصول به سبد خرید اضافه شد',
            'added_count': added_count
        })


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        store = get_current_store(self.request)
        product_id = self.request.query_params.get('product', None)
        
        if store and product_id:
            return Comment.objects.filter(
                product__store=store,
                product_id=product_id,
                is_approved=True
            )
        return Comment.objects.none()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def helpful(self, request, pk=None):
        """Mark comment as helpful"""
        comment = self.get_object()
        comment.helpful_count += 1
        comment.save()
        return Response({'message': 'نظر مفید بود'})


class RatingViewSet(viewsets.ModelViewSet):
    serializer_class = RatingSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        store = get_current_store(self.request)
        product_id = self.request.query_params.get('product', None)
        
        if store and product_id:
            return Rating.objects.filter(
                product__store=store,
                product_id=product_id
            )
        return Rating.objects.none()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get rating summary for a product"""
        product_id = request.query_params.get('product')
        if not product_id:
            return Response({'error': 'محصول مشخص نشده'}, status=status.HTTP_400_BAD_REQUEST)
        
        ratings = self.get_queryset()
        if ratings:
            avg_rating = ratings.aggregate(avg=Avg('score'))['avg']
            rating_counts = ratings.values('score').annotate(count=Count('score'))
            
            return Response({
                'average_rating': round(avg_rating, 1) if avg_rating else 0,
                'total_ratings': ratings.count(),
                'rating_distribution': {item['score']: item['count'] for item in rating_counts}
            })
        
        return Response({
            'average_rating': 0,
            'total_ratings': 0,
            'rating_distribution': {}
        })


class BulkImportLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BulkImportLogSerializer
    permission_classes = [IsStoreOwner]
    ordering = ['-created_at']

    def get_queryset(self):
        store = get_current_store(self.request)
        if store:
            return BulkImportLog.objects.filter(store=store)
        return BulkImportLog.objects.none()
