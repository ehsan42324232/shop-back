from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404
from shop.models import Store, Category, Product, ProductImage, Comment, Rating
from shop.storefront_models import Basket, Order, OrderItem
from shop.serializers import (
    StoreSerializer, CategorySerializer, ProductListSerializer, ProductDetailSerializer,
    ProductImageSerializer, CommentSerializer, RatingSerializer, BasketSerializer,
    OrderSerializer, CreateOrderSerializer, UserSerializer, ProductSerializer
)

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
