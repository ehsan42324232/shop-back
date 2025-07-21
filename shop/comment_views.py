from django.db import models, transaction
from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
import uuid

from .models import Product, Store
from .storefront_models import Order, OrderItem
from .middleware import get_current_store


class ProductReview(models.Model):
    """
    Product review model
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    customer = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, null=True, blank=True)
    
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])
    title = models.CharField(max_length=200)
    comment = models.TextField()
    
    # Review status
    STATUS_CHOICES = [
        ('pending', 'در انتظار تأیید'),
        ('approved', 'تأیید شده'),
        ('rejected', 'رد شده'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Helpful votes
    helpful_count = models.PositiveIntegerField(default=0)
    unhelpful_count = models.PositiveIntegerField(default=0)
    
    # Review attributes
    pros = models.TextField(blank=True, help_text='نقاط مثبت')
    cons = models.TextField(blank=True, help_text='نقاط منفی')
    
    # Purchase verification
    verified_purchase = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['product', 'customer', 'order_item']
        ordering = ['-created_at']

    def __str__(self):
        return f'نظر {self.customer.username} برای {self.product.name}'

    def save(self, *args, **kwargs):
        # Set verified purchase if order item exists
        if self.order_item and self.order_item.order.customer == self.customer:
            self.verified_purchase = True
        
        super().save(*args, **kwargs)
        
        # Update product rating
        self.update_product_rating()

    def update_product_rating(self):
        """Update product average rating"""
        approved_reviews = ProductReview.objects.filter(
            product=self.product,
            status='approved'
        )
        
        avg_rating = approved_reviews.aggregate(Avg('rating'))['rating__avg']
        review_count = approved_reviews.count()
        
        self.product.average_rating = avg_rating or 0
        self.product.review_count = review_count
        self.product.save(update_fields=['average_rating', 'review_count'])


class ReviewHelpful(models.Model):
    """
    Track helpful votes for reviews
    """
    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE)
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    is_helpful = models.BooleanField()  # True for helpful, False for unhelpful
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['review', 'user']


# Serializers
from rest_framework import serializers

class ProductReviewSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    customer_username = serializers.CharField(source='customer.username', read_only=True)
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductReview
        fields = [
            'id', 'rating', 'title', 'comment', 'pros', 'cons',
            'verified_purchase', 'helpful_count', 'unhelpful_count',
            'created_at', 'status', 'customer_name', 'customer_username',
            'can_edit', 'can_delete'
        ]
        read_only_fields = ['verified_purchase', 'helpful_count', 'unhelpful_count', 'status']

    def get_can_edit(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.customer == request.user and obj.status == 'pending'
        return False

    def get_can_delete(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.customer == request.user
        return False

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError('امتیاز باید بین 1 تا 5 باشد')
        return value

    def validate(self, data):
        request = self.context.get('request')
        product_id = self.context.get('product_id')
        
        if request and product_id:
            # Check if user already reviewed this product
            existing_review = ProductReview.objects.filter(
                product_id=product_id,
                customer=request.user
            ).exclude(id=self.instance.id if self.instance else None)
            
            if existing_review.exists():
                raise serializers.ValidationError('شما قبلاً برای این محصول نظر ثبت کرده‌اید')
        
        return data


class ProductReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet for product reviews
    """
    serializer_class = ProductReviewSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        product_id = self.kwargs.get('product_id')
        if product_id:
            queryset = ProductReview.objects.filter(product_id=product_id)
            
            # Only show approved reviews to non-owners
            if not (self.request.user.is_authenticated and 
                   hasattr(self.request.user, 'owned_store')):
                queryset = queryset.filter(status='approved')
            
            return queryset.order_by('-created_at')
        return ProductReview.objects.none()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['product_id'] = self.kwargs.get('product_id')
        return context

    def perform_create(self, serializer):
        product_id = self.kwargs.get('product_id')
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            raise serializers.ValidationError('محصول یافت نشد')

        # Check if user has purchased this product
        order_item = None
        purchased_items = OrderItem.objects.filter(
            product=product,
            order__customer=self.request.user,
            order__status='delivered'
        ).first()
        
        if purchased_items:
            order_item = purchased_items

        serializer.save(
            product=product,
            customer=self.request.user,
            order_item=order_item
        )

    @action(detail=True, methods=['post'])
    def mark_helpful(self, request, product_id=None, pk=None):
        """
        Mark review as helpful or unhelpful
        """
        review = self.get_object()
        is_helpful = request.data.get('is_helpful', True)
        
        # Remove existing vote if any
        ReviewHelpful.objects.filter(
            review=review,
            user=request.user
        ).delete()
        
        # Add new vote
        ReviewHelpful.objects.create(
            review=review,
            user=request.user,
            is_helpful=is_helpful
        )
        
        # Update counts
        helpful_count = ReviewHelpful.objects.filter(
            review=review,
            is_helpful=True
        ).count()
        
        unhelpful_count = ReviewHelpful.objects.filter(
            review=review,
            is_helpful=False
        ).count()
        
        review.helpful_count = helpful_count
        review.unhelpful_count = unhelpful_count
        review.save()
        
        return Response({
            'helpful_count': helpful_count,
            'unhelpful_count': unhelpful_count
        })

    @action(detail=False, methods=['get'])
    def summary(self, request, product_id=None):
        """
        Get review summary for a product
        """
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({'error': 'محصول یافت نشد'}, status=404)

        reviews = ProductReview.objects.filter(
            product=product,
            status='approved'
        )

        # Rating distribution
        rating_distribution = {}
        for i in range(1, 6):
            rating_distribution[str(i)] = reviews.filter(rating=i).count()

        # Overall stats
        total_reviews = reviews.count()
        average_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
        
        # Recommendation percentage
        recommend_count = reviews.filter(rating__gte=4).count()
        recommend_percentage = (recommend_count / total_reviews * 100) if total_reviews > 0 else 0

        return Response({
            'total_reviews': total_reviews,
            'average_rating': round(average_rating, 1),
            'rating_distribution': rating_distribution,
            'recommend_percentage': round(recommend_percentage, 1),
            'has_reviews': total_reviews > 0
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_reviews(request):
    """
    Get pending reviews for store owner
    """
    store = get_current_store(request)
    if not store:
        return Response({'error': 'Store not found'}, status=404)

    # Check if user is store owner
    if not hasattr(request.user, 'owned_store') or request.user.owned_store != store:
        return Response(
            {'error': 'Only store owners can view pending reviews'},
            status=status.HTTP_403_FORBIDDEN
        )

    pending_reviews = ProductReview.objects.filter(
        product__store=store,
        status='pending'
    ).select_related('product', 'customer').order_by('-created_at')

    paginator = Paginator(pending_reviews, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    reviews_data = []
    for review in page_obj:
        reviews_data.append({
            'id': review.id,
            'product_name': review.product.name,
            'customer_name': review.customer.get_full_name() or review.customer.username,
            'rating': review.rating,
            'title': review.title,
            'comment': review.comment,
            'created_at': review.created_at,
            'verified_purchase': review.verified_purchase
        })

    return Response({
        'reviews': reviews_data,
        'pagination': {
            'current_page': page_obj.number,
            'total_pages': paginator.num_pages,
            'total_reviews': paginator.count,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous()
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def moderate_review(request, review_id):
    """
    Approve or reject a review
    """
    try:
        review = ProductReview.objects.get(id=review_id)
    except ProductReview.DoesNotExist:
        return Response({'error': 'نظر یافت نشد'}, status=404)

    store = get_current_store(request)
    if not store or review.product.store != store:
        return Response({'error': 'دسترسی غیرمجاز'}, status=403)

    # Check if user is store owner
    if not hasattr(request.user, 'owned_store') or request.user.owned_store != store:
        return Response(
            {'error': 'فقط صاحب فروشگاه می‌تواند نظرات را تأیید کند'},
            status=status.HTTP_403_FORBIDDEN
        )

    action = request.data.get('action')  # 'approve' or 'reject'
    admin_note = request.data.get('admin_note', '')

    if action not in ['approve', 'reject']:
        return Response({'error': 'عمل نامعتبر'}, status=400)

    review.status = 'approved' if action == 'approve' else 'rejected'
    review.admin_notes = admin_note
    
    if action == 'approve':
        review.approved_at = timezone.now()
    
    review.save()

    return Response({
        'message': f'نظر با موفقیت {"تأیید" if action == "approve" else "رد"} شد',
        'review_id': review.id,
        'new_status': review.status
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_moderate_reviews(request):
    """
    Bulk approve or reject reviews
    """
    store = get_current_store(request)
    if not store:
        return Response({'error': 'Store not found'}, status=404)

    # Check if user is store owner
    if not hasattr(request.user, 'owned_store') or request.user.owned_store != store:
        return Response(
            {'error': 'Only store owners can moderate reviews'},
            status=status.HTTP_403_FORBIDDEN
        )

    review_ids = request.data.get('review_ids', [])
    action = request.data.get('action')  # 'approve' or 'reject'

    if not review_ids or action not in ['approve', 'reject']:
        return Response({'error': 'پارامترهای نامعتبر'}, status=400)

    reviews = ProductReview.objects.filter(
        id__in=review_ids,
        product__store=store,
        status='pending'
    )

    updated_count = 0
    new_status = 'approved' if action == 'approve' else 'rejected'

    with transaction.atomic():
        for review in reviews:
            review.status = new_status
            if action == 'approve':
                review.approved_at = timezone.now()
            review.save()
            updated_count += 1

    return Response({
        'message': f'{updated_count} نظر با موفقیت {"تأیید" if action == "approve" else "رد"} شد',
        'updated_count': updated_count
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def product_reviews_stats(request, product_id):
    """
    Get detailed review statistics for a product
    """
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return Response({'error': 'محصول یافت نشد'}, status=404)

    reviews = ProductReview.objects.filter(
        product=product,
        status='approved'
    )

    # Basic stats
    total_reviews = reviews.count()
    if total_reviews == 0:
        return Response({
            'total_reviews': 0,
            'average_rating': 0,
            'rating_distribution': {str(i): 0 for i in range(1, 6)},
            'recent_reviews': []
        })

    average_rating = reviews.aggregate(Avg('rating'))['rating__avg']
    
    # Rating distribution
    rating_distribution = {}
    for i in range(1, 6):
        count = reviews.filter(rating=i).count()
        rating_distribution[str(i)] = {
            'count': count,
            'percentage': round((count / total_reviews) * 100, 1)
        }

    # Recent reviews
    recent_reviews = reviews.order_by('-created_at')[:5]
    recent_reviews_data = []
    
    for review in recent_reviews:
        recent_reviews_data.append({
            'id': review.id,
            'rating': review.rating,
            'title': review.title,
            'comment': review.comment[:200] + '...' if len(review.comment) > 200 else review.comment,
            'customer_name': review.customer.get_full_name() or review.customer.username,
            'verified_purchase': review.verified_purchase,
            'helpful_count': review.helpful_count,
            'created_at': review.created_at
        })

    # Most helpful reviews
    helpful_reviews = reviews.filter(helpful_count__gt=0).order_by('-helpful_count')[:3]
    helpful_reviews_data = []
    
    for review in helpful_reviews:
        helpful_reviews_data.append({
            'id': review.id,
            'rating': review.rating,
            'title': review.title,
            'comment': review.comment,
            'customer_name': review.customer.get_full_name() or review.customer.username,
            'helpful_count': review.helpful_count,
            'verified_purchase': review.verified_purchase
        })

    return Response({
        'total_reviews': total_reviews,
        'average_rating': round(average_rating, 1),
        'rating_distribution': rating_distribution,
        'recent_reviews': recent_reviews_data,
        'helpful_reviews': helpful_reviews_data,
        'verified_purchases_count': reviews.filter(verified_purchase=True).count()
    })
