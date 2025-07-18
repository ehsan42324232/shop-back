from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
import json

from shop.models import Store, Category, Product, ProductImage, Comment, Rating, ProductAttribute, ProductAttributeValue
from shop.storefront_models import Basket, Order, OrderItem
from shop.serializers import (
    StoreSerializer, CategorySerializer, ProductListSerializer, ProductDetailSerializer,
    ProductImageSerializer, CommentSerializer, RatingSerializer, BasketSerializer,
    OrderSerializer, CreateOrderSerializer, UserSerializer, ProductSerializer
)


# Error Handlers
def handler404(request, exception=None):
    """Custom 404 handler"""
    if request.path.startswith('/api/'):
        return JsonResponse({
            'error': 'Resource not found',
            'status_code': 404
        }, status=404)
    return HttpResponse('<h1>Page Not Found</h1><p>The requested page could not be found.</p>', status=404)


def handler500(request):
    """Custom 500 handler"""
    if request.path.startswith('/api/'):
        return JsonResponse({
            'error': 'Internal server error',
            'status_code': 500
        }, status=500)
    return HttpResponse('<h1>Server Error</h1><p>Something went wrong on our end.</p>', status=500)


# ViewSets (these are the ones imported by urls.py)
class StoreViewSet(viewsets.ModelViewSet):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
    
    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        store = self.get_object()
        products = store.products.all()
        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        queryset = Category.objects.all()
        store_id = self.request.query_params.get('store')
        if store_id:
            queryset = queryset.filter(store_id=store_id)
        return queryset


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductListSerializer
    
    def get_queryset(self):
        queryset = Product.objects.all()
        store_id = self.request.query_params.get('store')
        category_id = self.request.query_params.get('category')
        search = self.request.query_params.get('search')
        
        if store_id:
            queryset = queryset.filter(store_id=store_id)
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        if search:
            queryset = queryset.filter(title__icontains=search)
        
        return queryset
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def add_comment(self, request, pk=None):
        product = self.get_object()
        serializer = CommentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user, product=product)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def add_rating(self, request, pk=None):
        product = self.get_object()
        # Remove existing rating if exists
        Rating.objects.filter(user=request.user, product=product).delete()
        
        serializer = RatingSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user, product=product)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BasketViewSet(viewsets.ModelViewSet):
    serializer_class = BasketSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Basket.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        # Check if item already exists in basket
        product_id = serializer.validated_data['product_id']
        existing_item = Basket.objects.filter(
            user=self.request.user, 
            product_id=product_id
        ).first()
        
        if existing_item:
            existing_item.quantity += serializer.validated_data.get('quantity', 1)
            existing_item.save()
            serializer.instance = existing_item
        else:
            serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['delete'])
    def clear(self, request):
        self.get_queryset().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)
    
    def create(self, request):
        serializer = CreateOrderSerializer(data=request.data)
        if serializer.is_valid():
            store_id = serializer.validated_data['store_id']
            
            # Get user's basket items for this store
            basket_items = Basket.objects.filter(
                user=request.user,
                product__store_id=store_id
            )
            
            if not basket_items.exists():
                return Response(
                    {'error': 'No items in basket for this store'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            with transaction.atomic():
                # Get store
                store = get_object_or_404(Store, id=store_id)
                
                # Calculate total amount
                total_amount = sum(
                    item.quantity * item.product.price 
                    for item in basket_items
                )
                
                # Create order
                order = Order.objects.create(
                    user=request.user,
                    store=store,
                    total_amount=total_amount,
                    customer_name=f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
                    customer_email=request.user.email,
                )
                
                # Create order items
                for basket_item in basket_items:
                    OrderItem.objects.create(
                        order=order,
                        product=basket_item.product,
                        quantity=basket_item.quantity,
                        price_at_order=basket_item.product.price
                    )
                    
                    # Update product stock if tracking is enabled
                    if basket_item.product.track_inventory:
                        product = basket_item.product
                        product.stock -= basket_item.quantity
                        product.save()
                
                # Clear basket items for this store
                basket_items.delete()
                
                return Response(
                    OrderSerializer(order).data, 
                    status=status.HTTP_201_CREATED
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Admin Views
class AdminStoreListView(generics.ListAPIView):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAdminUser]


class AdminStoreDetailView(generics.RetrieveUpdateAPIView):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAdminUser]


# Store Management Views  
class StoreListCreateView(generics.ListCreateAPIView):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class StoreDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


# Category Views
class CategoryListCreateView(generics.ListCreateAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


# Product Views
class ProductListCreateView(generics.ListCreateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductListSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductDetailSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


# Product Images
class ProductImageListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductImageSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        product_id = self.kwargs['product_id']
        return ProductImage.objects.filter(product_id=product_id)


# Product Comments and Ratings
class ProductCommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        product_id = self.kwargs['product_id']
        return Comment.objects.filter(product_id=product_id, is_approved=True)


class ProductRatingCreateView(generics.CreateAPIView):
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticated]


# Attribute Views
class AttributeListCreateView(generics.ListCreateAPIView):
    queryset = ProductAttribute.objects.all()
    serializer_class = ProductSerializer  # You'll need to create ProductAttributeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class AttributeDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProductAttribute.objects.all()
    serializer_class = ProductSerializer  # You'll need to create ProductAttributeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


# Function-based views for specific endpoints
@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def approve_store(request, store_id):
    try:
        store = get_object_or_404(Store, id=store_id)
        store.is_approved = True
        store.is_active = True
        store.approved_at = timezone.now()
        store.save()
        return Response({'message': 'Store approved successfully'})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def reject_store(request, store_id):
    try:
        store = get_object_or_404(Store, id=store_id)
        store.is_approved = False
        store.is_active = False
        store.save()
        return Response({'message': 'Store rejected successfully'})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_store_profile(request):
    try:
        if not hasattr(request, 'store') or not request.store:
            return Response({'error': 'Store not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = StoreSerializer(request.store)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def update_store_profile(request):
    try:
        if not hasattr(request, 'store') or not request.store:
            return Response({'error': 'Store not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = StoreSerializer(request.store, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_store_settings(request):
    try:
        if not hasattr(request, 'store') or not request.store:
            return Response({'error': 'Store not found'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            'currency': request.store.currency,
            'tax_rate': request.store.tax_rate,
            'is_active': request.store.is_active,
            'is_approved': request.store.is_approved,
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_store_analytics(request):
    try:
        if not hasattr(request, 'store') or not request.store:
            return Response({'error': 'Store not found'}, status=status.HTTP_404_NOT_FOUND)
        
        from .utils import get_store_analytics
        analytics = get_store_analytics(request.store)
        return Response(analytics)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_store_info(request):
    try:
        if not hasattr(request, 'store') or not request.store:
            return Response({'error': 'Store not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = StoreSerializer(request.store)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def search_products(request):
    try:
        if not hasattr(request, 'store') or not request.store:
            return Response({'error': 'Store not found'}, status=status.HTTP_404_NOT_FOUND)
        
        from .additional_views import ProductSearchView
        view = ProductSearchView()
        view.request = request
        return view.get(request)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_category_products(request, category_id):
    try:
        category = get_object_or_404(Category, id=category_id)
        products = category.products.filter(is_active=True)
        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_product_attributes(request, product_id):
    try:
        product = get_object_or_404(Product, id=product_id)
        attributes = product.attribute_values.all()
        data = [
            {
                'attribute_name': attr.attribute.name,
                'value': attr.value
            }
            for attr in attributes
        ]
        return Response(data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def update_product_stock(request, product_id):
    try:
        product = get_object_or_404(Product, id=product_id)
        new_stock = request.data.get('stock')
        
        if new_stock is not None:
            product.stock = new_stock
            product.save()
            return Response({'message': 'Stock updated successfully'})
        
        return Response({'error': 'Stock value required'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_store_products(request, store_id):
    try:
        store = get_object_or_404(Store, id=store_id)
        products = store.products.filter(is_active=True)
        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# Generic API Views (for backward compatibility)
class StoreListAPIView(generics.ListAPIView):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer

class ProductListAPIView(generics.ListAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

class ProductDetailAPIView(generics.RetrieveAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    lookup_field = 'id'

class StoreDomainProductListAPIView(generics.ListAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        domain = self.request.headers.get('X-Store-Domain')
        return Product.objects.filter(store__domain=domain)

class CategoryListByDomainAPIView(generics.ListAPIView):
    serializer_class = CategorySerializer

    def get_queryset(self):
        domain = self.request.headers.get('X-Store-Domain')
        return Category.objects.filter(store__domain=domain)

class StoreInfoByDomainAPIView(generics.RetrieveAPIView):
    serializer_class = StoreSerializer

    def get_object(self):
        domain = self.request.headers.get('X-Store-Domain')
        return Store.objects.get(domain=domain)
