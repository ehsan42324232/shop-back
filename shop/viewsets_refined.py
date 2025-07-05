from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .models_refined import (
    Store, Category, Product, ProductImage, Comment, 
    Rating, Basket, Order, OrderItem
)
from .serializers_refined import (
    StoreSerializer, CategorySerializer, ProductListSerializer,
    ProductDetailSerializer, CommentSerializer, RatingSerializer,
    BasketItemSerializer, OrderSerializer, CreateOrderSerializer,
    UserSerializer, UserRegistrationSerializer, PasswordChangeSerializer
)


class StoreViewSet(viewsets.ModelViewSet):
    """Store management viewset"""
    queryset = Store.objects.filter(is_active=True)
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['currency', 'is_active']
    ordering = ['-created_at']
    
    def get_queryset(self):
        if self.action == 'list':
            # Only show user's own stores for list view
            return Store.objects.filter(owner=self.request.user, is_active=True)
        return super().get_queryset()
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class CategoryViewSet(viewsets.ModelViewSet):
    """Category management viewset"""
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['store', 'parent', 'is_active']
    ordering = ['sort_order', 'name']
    
    def get_queryset(self):
        # Filter by store if provided
        store_id = self.request.query_params.get('store')
        if store_id:
            return Category.objects.filter(store_id=store_id, is_active=True)
        return Category.objects.filter(is_active=True)
    
    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Get category tree structure"""
        store_id = request.query_params.get('store')
        if not store_id:
            return Response({'error': 'Store ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        root_categories = Category.objects.filter(
            store_id=store_id, parent=None, is_active=True
        ).order_by('sort_order', 'name')
        
        serializer = CategorySerializer(root_categories, many=True)
        return Response(serializer.data)


class ProductViewSet(viewsets.ModelViewSet):
    """Product management viewset"""
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['title', 'description', 'sku']
    filterset_fields = [
        'store', 'category', 'is_featured', 'is_active', 
        'is_digital', 'track_inventory'
    ]
    ordering_fields = ['created_at', 'price', 'title']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True).select_related(
            'store', 'category'
        ).prefetch_related('images', 'ratings')
        
        # Filter by price range
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
        
        # Filter by availability
        in_stock = self.request.query_params.get('in_stock')
        if in_stock == 'true':
            queryset = queryset.filter(stock__gt=0)
        elif in_stock == 'false':
            queryset = queryset.filter(stock=0)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductListSerializer
    
    def perform_create(self, serializer):
        # Ensure product is created in user's store
        store = Store.objects.filter(owner=self.request.user).first()
        if not store:
            raise ValidationError("User must have a store to create products")
        serializer.save(store=store)
    
    @action(detail=True, methods=['post'])
    def add_to_basket(self, request, pk=None):
        """Add product to user's basket"""
        product = self.get_object()
        quantity = int(request.data.get('quantity', 1))
        
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if product.is_out_of_stock:
            return Response(
                {'error': 'Product is out of stock'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        basket_item, created = Basket.objects.get_or_create(
            user=request.user,
            product=product,
            defaults={'quantity': quantity, 'price_at_add': product.price}
        )
        
        if not created:
            basket_item.quantity += quantity
            basket_item.save()
        
        serializer = BasketItemSerializer(basket_item)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured products"""
        featured_products = self.get_queryset().filter(is_featured=True)[:10]
        serializer = self.get_serializer(featured_products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Advanced product search"""
        query = request.query_params.get('q', '')
        if not query:
            return Response({'error': 'Search query is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        products = self.get_queryset().filter(
            title__icontains=query
        ) | self.get_queryset().filter(
            description__icontains=query
        )
        
        page = self.paginate_queryset(products)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)


class CommentViewSet(viewsets.ModelViewSet):
    """Product comments/reviews viewset"""
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['product', 'is_approved']
    ordering = ['-created_at']
    
    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Comment.objects.all()
        return Comment.objects.filter(is_approved=True)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class RatingViewSet(viewsets.ModelViewSet):
    """Product ratings viewset"""
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['product', 'score']
    
    def get_queryset(self):
        return Rating.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class BasketViewSet(viewsets.ModelViewSet):
    """Shopping basket viewset"""
    serializer_class = BasketItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Basket.objects.filter(user=self.request.user).select_related('product')
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get basket summary"""
        basket_items = self.get_queryset()
        total_items = sum(item.quantity for item in basket_items)
        total_price = sum(item.total_price for item in basket_items)
        
        return Response({
            'total_items': total_items,
            'total_price': total_price,
            'items_count': basket_items.count()
        })
    
    @action(detail=False, methods=['delete'])
    def clear(self, request):
        """Clear all items from basket"""
        self.get_queryset().delete()
        return Response({'message': 'Basket cleared'}, status=status.HTTP_204_NO_CONTENT)


class OrderViewSet(viewsets.ModelViewSet):
    """Order management viewset"""
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'is_paid', 'store']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).select_related('store', 'user')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateOrderSerializer
        return OrderSerializer
    
    def create(self, request, *args, **kwargs):
        """Create new order from basket items"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        orders = serializer.save()
        
        # Return the first order (or all orders if multiple stores)
        order_serializer = OrderSerializer(orders, many=True)
        return Response(order_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an order"""
        order = self.get_object()
        if order.status in ['shipped', 'delivered']:
            return Response(
                {'error': 'Cannot cancel shipped or delivered orders'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = 'cancelled'
        order.save()
        
        serializer = self.get_serializer(order)
        return Response(serializer.data)


class AuthViewSet(viewsets.ViewSet):
    """Authentication viewset"""
    permission_classes = [permissions.AllowAny]
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        """User registration"""
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def login(self, request):
        """User login"""
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response(
                {'error': 'Username and password required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = authenticate(username=username, password=password)
        if user:
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            })
        
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def change_password(self, request):
        """Change user password"""
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({'message': 'Password changed successfully'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def profile(self, request):
        """Get user profile"""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['put'], permission_classes=[permissions.IsAuthenticated])
    def update_profile(self, request):
        """Update user profile"""
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
