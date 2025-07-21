# Enhanced ViewSets for Product Attributes and Advanced Features

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction, models
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from itertools import product as itertools_product
from rest_framework import serializers

from .models import Store, Product, Category
from .models_with_attributes import (
    ProductAttribute, ProductAttributeValue, ProductVariant,
    ProductReview, DeliveryMethod, Shipment, StoreSettings,
    StoreBanner, Coupon
)
from .serializers_with_attributes import (
    ProductAttributeSerializer, ProductAttributeValueSerializer,
    ProductVariantSerializer, ProductWithVariantsSerializer,
    ProductReviewSerializer, DeliveryMethodSerializer,
    ShipmentSerializer, StoreSettingsSerializer,
    StoreBannerSerializer, CouponSerializer,
    BulkVariantCreateSerializer, BulkVariantUpdateSerializer
)
from .middleware import get_current_store


class ProductAttributeViewSet(viewsets.ModelViewSet):
    """ViewSet for managing product attributes"""
    serializer_class = ProductAttributeSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        store = get_current_store(self.request)
        if not store:
            return ProductAttribute.objects.none()
        
        # Only store owners can manage attributes
        if hasattr(self.request.user, 'owned_store') and self.request.user.owned_store == store:
            return ProductAttribute.objects.filter(store=store)
        
        return ProductAttribute.objects.none()
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['store'] = get_current_store(self.request)
        return context
    
    def perform_create(self, serializer):
        store = get_current_store(self.request)
        if not store or not hasattr(self.request.user, 'owned_store'):
            raise serializers.ValidationError('فقط صاحبان فروشگاه می‌توانند ویژگی اضافه کنند')
        
        serializer.save(store=store)
    
    @action(detail=True, methods=['post'])
    def add_value(self, request, pk=None):
        """Add a new value to the attribute"""
        attribute = self.get_object()
        serializer = ProductAttributeValueSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(attribute=attribute)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def values(self, request, pk=None):
        """Get all values for this attribute"""
        attribute = self.get_object()
        values = attribute.values.filter(is_active=True).order_by('display_order', 'value')
        serializer = ProductAttributeValueSerializer(values, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def reorder_values(self, request, pk=None):
        """Reorder attribute values"""
        attribute = self.get_object()
        value_orders = request.data.get('value_orders', [])
        
        with transaction.atomic():
            for item in value_orders:
                try:
                    value = attribute.values.get(id=item['id'])
                    value.display_order = item['order']
                    value.save()
                except ProductAttributeValue.DoesNotExist:
                    continue
        
        return Response({'message': 'ترتیب مقادیر با موفقیت به‌روزرسانی شد'})


class ProductVariantViewSet(viewsets.ModelViewSet):
    """ViewSet for managing product variants"""
    serializer_class = ProductVariantSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        store = get_current_store(self.request)
        if not store:
            return ProductVariant.objects.none()
        
        product_id = self.kwargs.get('product_id')
        if product_id:
            return ProductVariant.objects.filter(
                product_id=product_id,
                product__store=store
            )
        
        # Store owners can see all variants
        if hasattr(self.request.user, 'owned_store') and self.request.user.owned_store == store:
            return ProductVariant.objects.filter(product__store=store)
        
        return ProductVariant.objects.none()
    
    def perform_create(self, serializer):
        product_id = self.kwargs.get('product_id')
        if product_id:
            try:
                product = Product.objects.get(id=product_id)
                serializer.save(product=product)
            except Product.DoesNotExist:
                raise serializers.ValidationError('محصول یافت نشد')
    
    @action(detail=False, methods=['post'])
    def generate_all(self, request, product_id=None):
        """Generate all possible variants for a product"""
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({'error': 'محصول یافت نشد'}, status=404)
        
        # Get product attributes that are variations
        attributes = ProductAttribute.objects.filter(
            store=product.store,
            is_variation=True,
            is_active=True
        ).prefetch_related('values')
        
        if not attributes.exists():
            return Response({'error': 'هیچ ویژگی متغیری تعریف نشده'}, status=400)
        
        # Generate all combinations
        attribute_values_lists = []
        for attr in attributes:
            values = attr.values.filter(is_active=True)
            if values.exists():
                attribute_values_lists.append(list(values))
        
        if not attribute_values_lists:
            return Response({'error': 'مقادیر ویژگی یافت نشد'}, status=400)
        
        combinations = list(itertools_product(*attribute_values_lists))
        created_variants = []
        
        with transaction.atomic():
            for i, combination in enumerate(combinations):
                # Check if variant already exists
                existing = ProductVariant.objects.filter(
                    product=product,
                    attribute_values__in=combination
                ).annotate(
                    value_count=models.Count('attribute_values')
                ).filter(value_count=len(combination))
                
                if existing.exists():
                    continue
                
                # Create new variant
                variant = ProductVariant.objects.create(
                    product=product,
                    sku=f"{product.sku or product.id}-VAR-{i+1}",
                    price_adjustment=0,
                    stock_quantity=0
                )
                
                variant.attribute_values.set(combination)
                created_variants.append(variant)
        
        serializer = ProductVariantSerializer(created_variants, many=True)
        return Response({
            'message': f'{len(created_variants)} تنوع جدید ایجاد شد',
            'variants': serializer.data
        })
    
    @action(detail=False, methods=['post'])
    def bulk_update(self, request, product_id=None):
        """Bulk update variants"""
        serializer = BulkVariantUpdateSerializer(data=request.data)
        if serializer.is_valid():
            variant_ids = serializer.validated_data['variant_ids']
            updates = serializer.validated_data['updates']
            
            variants = ProductVariant.objects.filter(
                id__in=variant_ids,
                product_id=product_id
            )
            
            updated_count = variants.update(**updates)
            
            return Response({
                'message': f'{updated_count} تنوع با موفقیت به‌روزرسانی شد',
                'updated_count': updated_count
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProductWithVariantsViewSet(viewsets.ModelViewSet):
    """Enhanced product viewset with variants support"""
    serializer_class = ProductWithVariantsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        store = get_current_store(self.request)
        if not store:
            return Product.objects.none()
        
        return Product.objects.filter(store=store).prefetch_related(
            'variants', 'variants__attribute_values', 'variants__attribute_values__attribute'
        )
    
    @action(detail=True, methods=['post'])
    def clone_with_variants(self, request, pk=None):
        """Clone a product with all its variants"""
        original_product = self.get_object()
        
        with transaction.atomic():
            # Clone the product
            cloned_product = Product.objects.create(
                name=f"{original_product.name} (کپی)",
                description=original_product.description,
                price=original_product.price,
                category=original_product.category,
                store=original_product.store,
                brand=original_product.brand,
                weight=original_product.weight,
                dimensions=original_product.dimensions,
                track_stock=original_product.track_stock,
                low_stock_threshold=original_product.low_stock_threshold,
                is_active=False  # Cloned products start as inactive
            )
            
            # Clone variants
            for variant in original_product.variants.all():
                cloned_variant = ProductVariant.objects.create(
                    product=cloned_product,
                    sku=f"{cloned_product.id}-{variant.sku.split('-')[-1]}",
                    price_adjustment=variant.price_adjustment,
                    stock_quantity=0,  # Start with zero stock
                    weight=variant.weight,
                    barcode=variant.barcode,
                    cost_price=variant.cost_price,
                    is_active=variant.is_active
                )
                
                # Copy attribute values
                cloned_variant.attribute_values.set(variant.attribute_values.all())
        
        serializer = self.get_serializer(cloned_product)
        return Response({
            'message': 'محصول با موفقیت کپی شد',
            'product': serializer.data
        })


class EnhancedProductReviewViewSet(viewsets.ModelViewSet):
    """Enhanced review system with moderation"""
    serializer_class = ProductReviewSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'summary', 'stats']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        product_id = self.kwargs.get('product_id')
        if product_id:
            queryset = ProductReview.objects.filter(product_id=product_id)
            
            # Show only approved reviews to non-owners
            if not (self.request.user.is_authenticated and 
                   hasattr(self.request.user, 'owned_store')):
                queryset = queryset.filter(status='approved')
            
            return queryset.select_related('customer', 'product').order_by('-created_at')
        return ProductReview.objects.none()
    
    @action(detail=False, methods=['get'])
    def analytics(self, request, product_id=None):
        """Get review analytics for store owners"""
        store = get_current_store(request)
        if not store:
            return Response({'error': 'Store not found'}, status=404)
        
        # Check if user is store owner
        if not hasattr(request.user, 'owned_store') or request.user.owned_store != store:
            return Response(
                {'error': 'Only store owners can view analytics'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            product = Product.objects.get(id=product_id, store=store)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=404)
        
        from django.db.models import Avg, Count
        from datetime import datetime, timedelta
        
        # Date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        reviews = ProductReview.objects.filter(
            product=product,
            created_at__gte=start_date
        )
        
        # Review stats
        total_reviews = reviews.count()
        approved_reviews = reviews.filter(status='approved').count()
        pending_reviews = reviews.filter(status='pending').count()
        average_rating = reviews.filter(status='approved').aggregate(
            Avg('rating')
        )['rating__avg'] or 0
        
        # Rating distribution
        rating_distribution = {}
        for i in range(1, 6):
            rating_distribution[str(i)] = reviews.filter(
                status='approved', rating=i
            ).count()
        
        # Response time (time to moderate)
        moderated_reviews = reviews.filter(
            status__in=['approved', 'rejected'],
            approved_at__isnull=False
        )
        
        avg_response_time = None
        if moderated_reviews.exists():
            response_times = []
            for review in moderated_reviews:
                if review.approved_at:
                    delta = review.approved_at - review.created_at
                    response_times.append(delta.total_seconds() / 3600)  # Hours
            
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
        
        return Response({
            'summary': {
                'total_reviews': total_reviews,
                'approved_reviews': approved_reviews,
                'pending_reviews': pending_reviews,
                'average_rating': round(average_rating, 1),
                'approval_rate': round((approved_reviews / total_reviews * 100), 1) if total_reviews > 0 else 0,
                'avg_response_time_hours': round(avg_response_time, 1) if avg_response_time else None
            },
            'rating_distribution': rating_distribution,
            'period_days': days
        })


class StoreManagementViewSet(viewsets.ModelViewSet):
    """Advanced store management with settings"""
    serializer_class = StoreSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        store = get_current_store(self.request)
        if not store:
            return StoreSettings.objects.none()
        
        # Only store owners can access settings
        if hasattr(self.request.user, 'owned_store') and self.request.user.owned_store == store:
            return StoreSettings.objects.filter(store=store)
        
        return StoreSettings.objects.none()
    
    def get_object(self):
        store = get_current_store(self.request)
        settings, created = StoreSettings.objects.get_or_create(store=store)
        return settings
    
    @action(detail=False, methods=['post'])
    def test_settings(self, request):
        """Test store settings like analytics IDs"""
        settings_data = request.data
        results = {}
        
        # Test Google Analytics
        if 'google_analytics_id' in settings_data:
            ga_id = settings_data['google_analytics_id']
            # Add GA validation logic here
            results['google_analytics'] = {
                'valid': bool(ga_id and (ga_id.startswith('UA-') or ga_id.startswith('G-'))),
                'message': 'شناسه معتبر است' if ga_id else 'شناسه وارد نشده'
            }
        
        # Test social media URLs
        social_urls = ['facebook_url', 'instagram_url', 'telegram_url']
        for url_field in social_urls:
            if url_field in settings_data:
                url = settings_data[url_field]
                results[url_field] = {
                    'valid': bool(url and url.startswith(('http://', 'https://'))),
                    'message': 'آدرس معتبر است' if url else 'آدرس وارد نشده'
                }
        
        return Response({
            'test_results': results,
            'overall_status': 'success' if all(r.get('valid', True) for r in results.values()) else 'warning'
        })


class StoreBannerViewSet(viewsets.ModelViewSet):
    """Manage store promotional banners"""
    serializer_class = StoreBannerSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        store = get_current_store(self.request)
        if not store:
            return StoreBanner.objects.none()
        
        # Store owners can manage all banners
        if hasattr(self.request.user, 'owned_store') and self.request.user.owned_store == store:
            return StoreBanner.objects.filter(store=store)
        
        # Public can see only active banners
        return StoreBanner.objects.filter(
            store=store,
            is_active=True
        ).filter(
            models.Q(start_date__isnull=True) | models.Q(start_date__lte=timezone.now())
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=timezone.now())
        )
    
    def perform_create(self, serializer):
        store = get_current_store(self.request)
        serializer.save(store=store)
    
    @action(detail=False, methods=['get'])
    def by_position(self, request):
        """Get banners by position"""
        position = request.GET.get('position')
        if not position:
            return Response({'error': 'Position parameter required'}, status=400)
        
        banners = self.get_queryset().filter(position=position)
        serializer = self.get_serializer(banners, many=True)
        return Response(serializer.data)


class CouponViewSet(viewsets.ModelViewSet):
    """Manage discount coupons"""
    serializer_class = CouponSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        store = get_current_store(self.request)
        if not store:
            return Coupon.objects.none()
        
        # Only store owners can manage coupons
        if hasattr(self.request.user, 'owned_store') and self.request.user.owned_store == store:
            return Coupon.objects.filter(store=store)
        
        return Coupon.objects.none()
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['store'] = get_current_store(self.request)
        return context
    
    def perform_create(self, serializer):
        store = get_current_store(self.request)
        serializer.save(store=store)
    
    @action(detail=False, methods=['post'])
    def validate_coupon(self, request):
        """Validate a coupon code"""
        code = request.data.get('code', '').upper()
        order_total = float(request.data.get('order_total', 0))
        
        store = get_current_store(request)
        if not store:
            return Response({'error': 'Store not found'}, status=404)
        
        try:
            coupon = Coupon.objects.get(store=store, code=code)
        except Coupon.DoesNotExist:
            return Response({
                'valid': False,
                'message': 'کوپن یافت نشد'
            })
        
        is_valid, message = coupon.is_valid(request.user, order_total)
        
        result = {
            'valid': is_valid,
            'message': message
        }
        
        if is_valid:
            discount_amount = coupon.calculate_discount(order_total)
            result.update({
                'coupon': {
                    'id': coupon.id,
                    'code': coupon.code,
                    'name': coupon.name,
                    'discount_type': coupon.discount_type,
                    'discount_value': float(coupon.discount_value)
                },
                'discount_amount': float(discount_amount),
                'final_total': float(order_total - discount_amount)
            })
        
        return Response(result)
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate a coupon with new code"""
        original_coupon = self.get_object()
        new_code = request.data.get('new_code', f"{original_coupon.code}-COPY")
        
        # Check if new code already exists
        if Coupon.objects.filter(store=original_coupon.store, code=new_code).exists():
            return Response({
                'error': 'کد کوپن جدید قبلاً استفاده شده'
            }, status=400)
        
        # Create duplicate
        cloned_coupon = Coupon.objects.create(
            store=original_coupon.store,
            code=new_code,
            name=f"{original_coupon.name} (کپی)",
            description=original_coupon.description,
            discount_type=original_coupon.discount_type,
            discount_value=original_coupon.discount_value,
            usage_limit=original_coupon.usage_limit,
            user_usage_limit=original_coupon.user_usage_limit,
            minimum_amount=original_coupon.minimum_amount,
            maximum_discount=original_coupon.maximum_discount,
            start_date=timezone.now(),
            end_date=original_coupon.end_date,
            is_active=False  # Start as inactive
        )
        
        serializer = self.get_serializer(cloned_coupon)
        return Response({
            'message': 'کوپن با موفقیت کپی شد',
            'coupon': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get coupon usage analytics"""
        store = get_current_store(request)
        if not store:
            return Response({'error': 'Store not found'}, status=404)
        
        from django.db.models import Sum, Count
        from datetime import datetime, timedelta
        
        # Date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        coupons = Coupon.objects.filter(store=store)
        
        # Usage stats
        total_coupons = coupons.count()
        active_coupons = coupons.filter(is_active=True).count()
        
        # Most used coupons
        most_used = coupons.annotate(
            usage_rate=models.F('usage_count')
        ).order_by('-usage_rate')[:10]
        
        most_used_data = []
        for coupon in most_used:
            most_used_data.append({
                'code': coupon.code,
                'name': coupon.name,
                'usage_count': coupon.usage_count,
                'usage_limit': coupon.usage_limit,
                'usage_percentage': (coupon.usage_count / coupon.usage_limit * 100) if coupon.usage_limit else 0
            })
        
        return Response({
            'summary': {
                'total_coupons': total_coupons,
                'active_coupons': active_coupons,
                'period_days': days
            },
            'most_used_coupons': most_used_data
        })
