from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from .models_with_attributes import Store, Category, Product, ProductAttribute
from .serializers_with_attributes import (
    StoreSerializer, CategorySerializer, ProductListSerializer,
    ProductDetailSerializer, ProductAttributeSerializer
)


class StorefrontViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public API for store-specific storefronts
    """
    permission_classes = [permissions.AllowAny]
    
    def get_store(self):
        """Get store from request context"""
        if hasattr(self.request, 'store') and self.request.store:
            return self.request.store
        return None
    
    @action(detail=False, methods=['get'])
    def info(self, request):
        """Get store information"""
        store = self.get_store()
        if not store:
            return Response(
                {'error': 'Store not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = StoreSerializer(store)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def categories(self, request):
        """Get store categories"""
        store = self.get_store()
        if not store:
            return Response(
                {'error': 'Store not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get root categories (no parent)
        root_categories = Category.objects.filter(
            store=store, 
            parent=None, 
            is_active=True
        ).order_by('sort_order', 'name')
        
        serializer = CategorySerializer(root_categories, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def category_tree(self, request):
        """Get complete category tree"""
        store = self.get_store()
        if not store:
            return Response(
                {'error': 'Store not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        def build_tree(parent=None):
            categories = Category.objects.filter(
                store=store, 
                parent=parent, 
                is_active=True
            ).order_by('sort_order', 'name')
            
            tree = []
            for category in categories:
                cat_data = CategorySerializer(category).data
                cat_data['children'] = build_tree(category)
                tree.append(cat_data)
            
            return tree
        
        tree = build_tree()
        return Response(tree)
    
    @action(detail=False, methods=['get'])
    def products(self, request):
        """Get store products with filtering"""
        store = self.get_store()
        if not store:
            return Response(
                {'error': 'Store not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Base queryset for store products
        queryset = Product.objects.filter(
            store=store, 
            is_active=True
        ).select_related('category').prefetch_related('images', 'attribute_values__attribute')
        
        # Apply filters
        category_id = request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Search filter
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | 
                Q(description__icontains=search) |
                Q(attribute_values__value__icontains=search)
            ).distinct()
        
        # Price filters
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
        
        # Stock filter
        in_stock = request.query_params.get('in_stock')
        if in_stock == 'true':
            queryset = queryset.filter(stock__gt=0)
        elif in_stock == 'false':
            queryset = queryset.filter(stock=0)
        
        # Attribute filters
        for key, value in request.query_params.items():
            if key.startswith('attr_'):
                attr_name = key[5:]  # Remove 'attr_' prefix
                queryset = queryset.filter(
                    attribute_values__attribute__name=attr_name,
                    attribute_values__value=value
                )
        
        # Featured filter
        featured = request.query_params.get('featured')
        if featured == 'true':
            queryset = queryset.filter(is_featured=True)
        
        # Ordering
        ordering = request.query_params.get('ordering', '-created_at')
        if ordering in ['price', '-price', 'title', '-title', 'created_at', '-created_at']:
            queryset = queryset.order_by(ordering)
        
        # Pagination
        page_size = min(int(request.query_params.get('page_size', 20)), 100)
        page = int(request.query_params.get('page', 1))
        
        start = (page - 1) * page_size
        end = start + page_size
        
        products = queryset[start:end]
        total = queryset.count()
        
        serializer = ProductListSerializer(products, many=True)
        
        return Response({
            'results': serializer.data,
            'total': total,
            'page': page,
            'page_size': page_size,
            'has_next': end < total,
            'has_previous': page > 1
        })
    
    @action(detail=False, methods=['get'])
    def product_detail(self, request):
        """Get product details"""
        store = self.get_store()
        if not store:
            return Response(
                {'error': 'Store not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        product_id = request.query_params.get('id')
        product_slug = request.query_params.get('slug')
        
        if not product_id and not product_slug:
            return Response(
                {'error': 'Product ID or slug required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            if product_id:
                product = Product.objects.get(id=product_id, store=store, is_active=True)
            else:
                product = Product.objects.get(slug=product_slug, store=store, is_active=True)
            
            serializer = ProductDetailSerializer(product)
            return Response(serializer.data)
            
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def featured_products(self, request):
        """Get featured products"""
        store = self.get_store()
        if not store:
            return Response(
                {'error': 'Store not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        limit = min(int(request.query_params.get('limit', 10)), 50)
        
        products = Product.objects.filter(
            store=store,
            is_active=True,
            is_featured=True
        ).order_by('-created_at')[:limit]
        
        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def attributes(self, request):
        """Get store attributes for filtering"""
        store = self.get_store()
        if not store:
            return Response(
                {'error': 'Store not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        attributes = ProductAttribute.objects.filter(
            store=store,
            is_filterable=True
        ).order_by('sort_order', 'name')
        
        serializer = ProductAttributeSerializer(attributes, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def search_suggestions(self, request):
        """Get search suggestions"""
        store = self.get_store()
        if not store:
            return Response(
                {'error': 'Store not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        query = request.query_params.get('q', '').strip()
        if not query or len(query) < 2:
            return Response([])
        
        # Get product title suggestions
        products = Product.objects.filter(
            store=store,
            is_active=True,
            title__icontains=query
        ).values_list('title', flat=True)[:5]
        
        # Get category suggestions
        categories = Category.objects.filter(
            store=store,
            is_active=True,
            name__icontains=query
        ).values_list('name', flat=True)[:3]
        
        suggestions = list(products) + list(categories)
        return Response(suggestions[:8])


class DomainConfigViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API for domain configuration and store settings
    """
    permission_classes = [permissions.AllowAny]
    
    @action(detail=False, methods=['get'])
    def store_config(self, request):
        """Get store configuration for domain"""
        store = getattr(request, 'store', None)
        if not store:
            return Response(
                {'error': 'Store not found for this domain'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        config = {
            'store': {
                'id': str(store.id),
                'name': store.name,
                'description': store.description,
                'domain': store.domain,
                'currency': store.currency,
                'tax_rate': float(store.tax_rate),
                'email': store.email,
                'phone': store.phone,
                'address': store.address,
                'logo': store.logo.url if store.logo else None,
            },
            'theme': getattr(request, 'theme_context', {}),
            'features': {
                'attributes_enabled': store.attributes.exists(),
                'categories_enabled': store.categories.exists(),
                'featured_products_enabled': store.products.filter(is_featured=True).exists(),
            }
        }
        
        return Response(config)
    
    @action(detail=False, methods=['get'])
    def domain_status(self, request):
        """Check domain status and configuration"""
        host = request.get_host()
        if ':' in host:
            host = host.split(':')[0]
        
        try:
            store = Store.objects.get(domain=host, is_active=True)
            return Response({
                'status': 'active',
                'store_id': str(store.id),
                'store_name': store.name,
                'domain': store.domain,
                'configured': True
            })
        except Store.DoesNotExist:
            return Response({
                'status': 'not_found',
                'domain': host,
                'configured': False,
                'message': 'No store found for this domain'
            })
