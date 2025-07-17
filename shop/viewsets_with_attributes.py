from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import Q
from rest_framework_simplejwt.tokens import RefreshToken
from .models_with_attributes import (
    Store, Category, Product, ProductAttribute, ProductAttributeValue,
    ProductImage, Comment, Rating, Basket, Order, OrderItem, BulkImportLog
)
from .serializers_with_attributes import (
    StoreSerializer, CategorySerializer, ProductListSerializer,
    ProductDetailSerializer, ProductAttributeSerializer, ProductAttributeValueSerializer,
    CommentSerializer, RatingSerializer, BasketItemSerializer, OrderSerializer, 
    CreateOrderSerializer, UserSerializer, UserRegistrationSerializer, 
    PasswordChangeSerializer, BulkImportLogSerializer, BulkImportSerializer
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

    @action(detail=True, methods=['get'])
    def attributes(self, request, pk=None):
        """Get store's product attributes"""
        store = self.get_object()
        attributes = store.attributes.all().order_by('sort_order', 'name')
        serializer = ProductAttributeSerializer(attributes, many=True)
        return Response(serializer.data)


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

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create multiple categories from hierarchy"""
        store_id = request.data.get('store_id')
        categories_data = request.data.get('categories', [])
        
        if not store_id:
            return Response({'error': 'Store ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            store = Store.objects.get(id=store_id)
        except Store.DoesNotExist:
            return Response({'error': 'Store not found'}, status=status.HTTP_404_NOT_FOUND)
        
        created_categories = []
        with transaction.atomic():
            for cat_data in categories_data:
                category, created = Category.objects.get_or_create(
                    store=store,
                    name=cat_data['name'],
                    defaults={
                        'description': cat_data.get('description', ''),
                        'parent_id': cat_data.get('parent_id'),
                        'sort_order': cat_data.get('sort_order', 0)
                    }
                )
                if created:
                    created_categories.append(category)
        
        serializer = CategorySerializer(created_categories, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProductAttributeViewSet(viewsets.ModelViewSet):
    """Product attributes management viewset"""
    serializer_class = ProductAttributeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name']
    filterset_fields = ['store', 'attribute_type', 'is_required', 'is_filterable']
    ordering = ['sort_order', 'name']
    
    def get_queryset(self):
        # Filter by store if provided
        store_id = self.request.query_params.get('store')
        if store_id:
            return ProductAttribute.objects.filter(store_id=store_id)
        return ProductAttribute.objects.all()
    
    def perform_create(self, serializer):
        # Ensure attribute is created in user's store
        store = Store.objects.filter(owner=self.request.user).first()
        if not store:
            raise ValidationError("User must have a store to create attributes")
        serializer.save(store=store)


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
        ).prefetch_related('images', 'ratings', 'attribute_values__attribute')
        
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
        
        # Filter by attributes
        for key, value in self.request.query_params.items():
            if key.startswith('attr_'):
                attr_name = key[5:]  # Remove 'attr_' prefix
                queryset = queryset.filter(
                    attribute_values__attribute__name=attr_name,
                    attribute_values__value=value
                )
        
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
    
    @action(detail=True, methods=['post', 'put'])
    def attributes(self, request, pk=None):
        """Set product attributes"""
        product = self.get_object()
        attributes_data = request.data.get('attributes', [])
        
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Check if user owns the product's store
        if product.store.owner != request.user:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        with transaction.atomic():
            # Clear existing attributes if PUT request
            if request.method == 'PUT':
                product.attribute_values.all().delete()
            
            # Add new attributes
            for attr_data in attributes_data:
                attribute_id = attr_data.get('attribute_id')
                value = attr_data.get('value')
                
                if not attribute_id or not value:
                    continue
                
                try:
                    attribute = ProductAttribute.objects.get(
                        id=attribute_id, 
                        store=product.store
                    )
                    
                    ProductAttributeValue.objects.update_or_create(
                        product=product,
                        attribute=attribute,
                        defaults={'value': value}
                    )
                except ProductAttribute.DoesNotExist:
                    continue
        
        # Return updated product attributes
        serializer = ProductAttributeValueSerializer(
            product.attribute_values.all(), 
            many=True
        )
        return Response(serializer.data)
    
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
            Q(title__icontains=query) | 
            Q(description__icontains=query) |
            Q(attribute_values__value__icontains=query)
        ).distinct()
        
        page = self.paginate_queryset(products)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def bulk_import(self, request):
        """Bulk import products from CSV/Excel"""
        serializer = BulkImportSerializer(data=request.data)
        if serializer.is_valid():
            # Process the import asynchronously (for now we'll do it synchronously)
            result = self._process_bulk_import(serializer.validated_data)
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def _process_bulk_import(self, validated_data):
        """Process bulk import file"""
        import csv
        import io
        import pandas as pd
        from django.core.files.storage import default_storage
        from django.utils.text import slugify
        from decimal import Decimal
        
        file = validated_data['file']
        store_id = validated_data['store_id']
        update_existing = validated_data['update_existing']
        create_categories = validated_data['create_categories']
        
        store = Store.objects.get(id=store_id)
        
        # Save file temporarily
        file_path = default_storage.save(f'imports/{file.name}', file)
        
        # Create import log
        import_log = BulkImportLog.objects.create(
            store=store,
            user=self.request.user,
            filename=file.name,
            file_path=file_path
        )
        
        try:
            # Read file
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
            
            import_log.total_rows = len(df)
            import_log.save()
            
            # Process each row
            for index, row in df.iterrows():
                try:
                    self._process_import_row(row, store, create_categories, update_existing, import_log)
                    import_log.successful_rows += 1
                except Exception as e:
                    import_log.failed_rows += 1
                    import_log.error_details.append({
                        'row': index + 1,
                        'error': str(e),
                        'data': row.to_dict()
                    })
                
                import_log.save()
            
            import_log.status = 'completed' if import_log.failed_rows == 0 else 'partial'
            import_log.save()
            
            return BulkImportLogSerializer(import_log).data
            
        except Exception as e:
            import_log.status = 'failed'
            import_log.error_details.append({'error': str(e)})
            import_log.save()
            raise e
    
    def _process_import_row(self, row, store, create_categories, update_existing, import_log):
        """Process a single import row"""
        with transaction.atomic():
            # Create/get category
            category = None
            if create_categories and 'category' in row and pd.notna(row['category']):
                category_path = str(row['category']).split(' > ')
                parent = None
                
                for cat_name in category_path:
                    cat_name = cat_name.strip()
                    category, created = Category.objects.get_or_create(
                        store=store,
                        name=cat_name,
                        parent=parent,
                        defaults={'slug': slugify(cat_name)}
                    )
                    if created:
                        import_log.categories_created += 1
                    parent = category
            
            # Create/update product
            product_data = {
                'title': row.get('title', ''),
                'description': row.get('description', ''),
                'price': Decimal(str(row.get('price', 0))),
                'sku': row.get('sku', ''),
                'stock': int(row.get('stock', 0)),
                'category': category,
                'store': store
            }
            
            # Check if product exists
            product = None
            if update_existing and 'sku' in row and pd.notna(row['sku']):
                product = Product.objects.filter(
                    store=store, 
                    sku=row['sku']
                ).first()
            
            if product:
                # Update existing product
                for key, value in product_data.items():
                    if key != 'store':  # Don't update store
                        setattr(product, key, value)
                product.save()
                import_log.products_updated += 1
            else:
                # Create new product
                product = Product.objects.create(**product_data)
                import_log.products_created += 1
            
            # Process attributes
            for col in row.index:
                if col.startswith('attr_'):
                    attr_name = col[5:]  # Remove 'attr_' prefix
                    attr_value = row[col]
                    
                    if pd.notna(attr_value):
                        # Get or create attribute
                        attribute, created = ProductAttribute.objects.get_or_create(
                            store=store,
                            name=attr_name,
                            defaults={
                                'attribute_type': 'text',
                                'slug': slugify(attr_name)
                            }
                        )
                        
                        # Set attribute value
                        ProductAttributeValue.objects.update_or_create(
                            product=product,
                            attribute=attribute,
                            defaults={'value': str(attr_value)}
                        )


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


class BulkImportLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Bulk import logs viewset"""
    serializer_class = BulkImportLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['store', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return BulkImportLog.objects.filter(user=self.request.user)


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
