# Public Storefront Views
# Customer-facing store website views

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q, Count, Avg
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Store
from .mall_models import EnhancedProduct, ProductInstance, EnhancedProductCategory

@api_view(['GET'])
@permission_classes([AllowAny])
def store_homepage(request, store_domain):
    """Public store homepage"""
    try:
        store = get_object_or_404(Store, domain=store_domain, is_active=True)
        
        # Get featured products
        featured_products = ProductInstance.objects.filter(
            product__store=store,
            product__is_active=True,
            is_active=True
        ).select_related('product')[:8]
        
        # Get categories
        categories = EnhancedProductCategory.objects.filter(
            store=store,
            is_active=True,
            level=0  # Root categories
        )[:6]
        
        return Response({
            'store': {
                'name': store.name,
                'description': store.description,
                'logo': store.logo.url if store.logo else None
            },
            'featured_products': [{
                'id': p.id,
                'name': p.product.name,
                'price': str(p.price),
                'compare_price': str(p.compare_price) if p.compare_price else None,
                'images': p.product.images[:1],  # First image only
                'is_on_sale': p.is_on_sale
            } for p in featured_products],
            'categories': [{
                'id': c.id,
                'name': c.name,
                'image': c.image.url if c.image else None
            } for c in categories]
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([AllowAny])
def store_products(request, store_domain):
    """Store products listing with filtering"""
    try:
        store = get_object_or_404(Store, domain=store_domain, is_active=True)
        
        # Get products
        products = ProductInstance.objects.filter(
            product__store=store,
            product__is_active=True,
            is_active=True
        ).select_related('product', 'product__category')
        
        # Apply filters
        category_id = request.GET.get('category')
        if category_id:
            products = products.filter(product__category_id=category_id)
        
        search = request.GET.get('search')
        if search:
            products = products.filter(
                Q(product__name__icontains=search) |
                Q(product__description__icontains=search)
            )
        
        # Apply sorting
        sort_by = request.GET.get('sort', 'newest')
        if sort_by == 'price_low':
            products = products.order_by('price')
        elif sort_by == 'price_high':
            products = products.order_by('-price')
        elif sort_by == 'newest':
            products = products.order_by('-created_at')
        
        # Pagination
        page = int(request.GET.get('page', 1))
        per_page = 12
        start = (page - 1) * per_page
        end = start + per_page
        
        products_page = products[start:end]
        total_count = products.count()
        
        return Response({
            'products': [{
                'id': p.id,
                'name': p.product.name,
                'price': str(p.price),
                'compare_price': str(p.compare_price) if p.compare_price else None,
                'images': p.product.images[:1],
                'category': p.product.category.name if p.product.category else None,
                'is_on_sale': p.is_on_sale,
                'discount_percentage': p.discount_percentage
            } for p in products_page],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_count,
                'pages': (total_count + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)