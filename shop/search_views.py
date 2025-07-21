from django.db import models
from django.db.models import Q, F, Value, IntegerField
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.core.cache import cache
import json

from .models import Product, Category, Store
from .serializers import ProductSerializer, CategorySerializer
from .middleware import get_current_store


class SearchResultsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ProductSearchView(generics.ListAPIView):
    """
    Advanced product search with filtering, sorting, and faceted search
    """
    serializer_class = ProductSerializer
    pagination_class = SearchResultsPagination
    permission_classes = [AllowAny]

    def get_queryset(self):
        store = get_current_store(self.request)
        if not store:
            return Product.objects.none()

        queryset = Product.objects.filter(
            store=store,
            is_active=True
        ).select_related('category', 'store').prefetch_related('images')

        # Search query
        search_query = self.request.GET.get('q', '').strip()
        if search_query:
            # Use PostgreSQL full-text search if available
            try:
                search_vector = SearchVector('name', 'description', 'tags')
                search_query_obj = SearchQuery(search_query, config='simple')
                queryset = queryset.annotate(
                    search=search_vector,
                    rank=SearchRank(search_vector, search_query_obj)
                ).filter(search=search_query_obj).order_by('-rank', '-created_at')
            except:
                # Fallback to icontains search
                queryset = queryset.filter(
                    Q(name__icontains=search_query) |
                    Q(description__icontains=search_query) |
                    Q(tags__icontains=search_query)
                ).distinct()

        # Category filtering
        category_id = self.request.GET.get('category')
        if category_id:
            try:
                category = Category.objects.get(id=category_id, store=store)
                # Include subcategories
                categories = [category]
                categories.extend(category.get_descendants())
                queryset = queryset.filter(category__in=categories)
            except Category.DoesNotExist:
                pass

        # Price range filtering
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        if min_price:
            try:
                queryset = queryset.filter(price__gte=float(min_price))
            except ValueError:
                pass
        if max_price:
            try:
                queryset = queryset.filter(price__lte=float(max_price))
            except ValueError:
                pass

        # Stock filtering
        in_stock = self.request.GET.get('in_stock')
        if in_stock == 'true':
            queryset = queryset.filter(stock_quantity__gt=0)
        elif in_stock == 'false':
            queryset = queryset.filter(stock_quantity=0)

        # Brand filtering
        brand = self.request.GET.get('brand')
        if brand:
            queryset = queryset.filter(brand__icontains=brand)

        # Tags filtering
        tags = self.request.GET.get('tags')
        if tags:
            tag_list = [tag.strip() for tag in tags.split(',')]
            for tag in tag_list:
                queryset = queryset.filter(tags__icontains=tag)

        # Sorting
        sort_by = self.request.GET.get('sort', 'created_at')
        sort_order = self.request.GET.get('order', 'desc')
        
        sort_options = {
            'name': 'name',
            'price': 'price',
            'created_at': 'created_at',
            'popularity': 'view_count',
            'rating': 'average_rating'
        }
        
        if sort_by in sort_options:
            order_prefix = '-' if sort_order == 'desc' else ''
            queryset = queryset.order_by(f'{order_prefix}{sort_options[sort_by]}')

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Get facets for filtering
        facets = self.get_search_facets(queryset, request)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['facets'] = facets
            return response

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'results': serializer.data,
            'facets': facets
        })

    def get_search_facets(self, queryset, request):
        """
        Generate facets for search filtering
        """
        store = get_current_store(request)
        cache_key = f"search_facets_{store.id if store else 'global'}"
        
        facets = cache.get(cache_key)
        if facets is None:
            # Categories facet
            categories = Category.objects.filter(
                store=store,
                product__in=queryset
            ).annotate(
                product_count=models.Count('product')
            ).filter(product_count__gt=0).order_by('name')

            # Price ranges facet
            price_ranges = self.get_price_ranges(queryset)

            # Brands facet
            brands = queryset.values('brand').annotate(
                count=models.Count('id')
            ).filter(brand__isnull=False, brand__gt='').order_by('brand')

            # Availability facet
            in_stock_count = queryset.filter(stock_quantity__gt=0).count()
            out_of_stock_count = queryset.filter(stock_quantity=0).count()

            facets = {
                'categories': [
                    {
                        'id': cat.id,
                        'name': cat.name,
                        'count': cat.product_count
                    } for cat in categories
                ],
                'price_ranges': price_ranges,
                'brands': [
                    {
                        'name': brand['brand'],
                        'count': brand['count']
                    } for brand in brands
                ],
                'availability': [
                    {'name': 'در انبار', 'value': 'true', 'count': in_stock_count},
                    {'name': 'ناموجود', 'value': 'false', 'count': out_of_stock_count}
                ]
            }
            
            cache.set(cache_key, facets, 300)  # Cache for 5 minutes
        
        return facets

    def get_price_ranges(self, queryset):
        """
        Generate dynamic price ranges based on product prices
        """
        prices = queryset.aggregate(
            min_price=models.Min('price'),
            max_price=models.Max('price')
        )
        
        if not prices['min_price'] or not prices['max_price']:
            return []

        min_price = float(prices['min_price'])
        max_price = float(prices['max_price'])
        
        # Create 5 price ranges
        range_size = (max_price - min_price) / 5
        ranges = []
        
        for i in range(5):
            range_min = min_price + (i * range_size)
            range_max = min_price + ((i + 1) * range_size)
            
            if i == 4:  # Last range includes max price
                range_max = max_price
            
            count = queryset.filter(
                price__gte=range_min,
                price__lte=range_max
            ).count()
            
            if count > 0:
                ranges.append({
                    'min': round(range_min, 0),
                    'max': round(range_max, 0),
                    'count': count,
                    'label': f"{int(range_min):,} - {int(range_max):,} تومان"
                })
        
        return ranges


@api_view(['GET'])
@permission_classes([AllowAny])
def search_suggestions(request):
    """
    Provide search suggestions based on query
    """
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return Response({'suggestions': []})

    store = get_current_store(request)
    if not store:
        return Response({'suggestions': []})

    cache_key = f"search_suggestions_{store.id}_{query}"
    suggestions = cache.get(cache_key)
    
    if suggestions is None:
        # Product name suggestions
        products = Product.objects.filter(
            store=store,
            is_active=True,
            name__icontains=query
        ).values_list('name', flat=True)[:5]

        # Category suggestions
        categories = Category.objects.filter(
            store=store,
            name__icontains=query
        ).values_list('name', flat=True)[:3]

        # Brand suggestions
        brands = Product.objects.filter(
            store=store,
            is_active=True,
            brand__icontains=query
        ).values_list('brand', flat=True).distinct()[:3]

        suggestions = {
            'products': list(products),
            'categories': list(categories),
            'brands': list(brands)
        }
        
        cache.set(cache_key, suggestions, 300)  # Cache for 5 minutes

    return Response({'suggestions': suggestions})


@api_view(['GET'])
@permission_classes([AllowAny])
def popular_searches(request):
    """
    Return popular search terms for the store
    """
    store = get_current_store(request)
    if not store:
        return Response({'popular_searches': []})

    # This would typically come from search analytics
    # For now, return popular categories and brands
    popular_categories = Category.objects.filter(
        store=store
    ).annotate(
        product_count=models.Count('product')
    ).filter(product_count__gt=0).order_by('-product_count')[:10]

    popular_brands = Product.objects.filter(
        store=store,
        is_active=True
    ).values('brand').annotate(
        count=models.Count('id')
    ).filter(brand__isnull=False, brand__gt='').order_by('-count')[:5]

    return Response({
        'popular_searches': {
            'categories': [cat.name for cat in popular_categories],
            'brands': [brand['brand'] for brand in popular_brands]
        }
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def log_search(request):
    """
    Log search queries for analytics
    """
    query = request.data.get('query', '').strip()
    results_count = request.data.get('results_count', 0)
    
    store = get_current_store(request)
    if not store or not query:
        return Response({'status': 'error'})

    # Here you would log to your analytics system
    # For now, we'll just return success
    
    return Response({'status': 'logged'})
