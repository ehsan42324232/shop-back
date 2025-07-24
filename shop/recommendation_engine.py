from django.db.models import Q, Count, Avg, Sum, F
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging

from .models import Product, ProductInstance, Order, OrderItem
from .customer_models import CustomerProfile, CustomerWishlist, CustomerReview
from .storefront_models import ProductView, SearchQuery

logger = logging.getLogger(__name__)


class ProductRecommendationEngine:
    """
    Advanced product recommendation engine for Iranian e-commerce platform
    Supports multiple recommendation strategies optimized for Persian market
    """
    
    def __init__(self):
        self.strategies = {
            'collaborative': self._collaborative_filtering,
            'content_based': self._content_based_filtering,
            'trending': self._trending_products,
            'popular': self._popular_products,
            'seasonal': self._seasonal_recommendations,
            'price_based': self._price_based_recommendations,
            'cross_sell': self._cross_sell_recommendations,
            'recently_viewed': self._recently_viewed_similar,
            'category_trending': self._category_trending,
            'user_behavior': self._user_behavior_based
        }
    
    def get_recommendations(
        self, 
        user: User = None, 
        product: Product = None,
        strategy: str = 'hybrid',
        limit: int = 10,
        exclude_owned: bool = True,
        store_id: int = None
    ) -> List[Dict[str, Any]]:
        """
        Get product recommendations using specified strategy
        
        Args:
            user: Target user for personalized recommendations
            product: Base product for related recommendations
            strategy: Recommendation strategy to use
            limit: Maximum number of recommendations
            exclude_owned: Whether to exclude products user already owns
            store_id: Filter by specific store
            
        Returns:
            List of recommended products with scores
        """
        try:
            if strategy == 'hybrid':
                return self._hybrid_recommendations(user, product, limit, exclude_owned, store_id)
            elif strategy in self.strategies:
                return self.strategies[strategy](user, product, limit, exclude_owned, store_id)
            else:
                logger.warning(f"Unknown strategy: {strategy}, falling back to popular")
                return self._popular_products(user, product, limit, exclude_owned, store_id)
                
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            return self._fallback_recommendations(limit, store_id)
    
    def _hybrid_recommendations(
        self, 
        user: User = None, 
        product: Product = None,
        limit: int = 10,
        exclude_owned: bool = True,
        store_id: int = None
    ) -> List[Dict[str, Any]]:
        """
        Hybrid recommendation combining multiple strategies
        """
        recommendations = {}
        
        # Weight for each strategy
        strategies_weights = {
            'collaborative': 0.3,
            'content_based': 0.25,
            'trending': 0.15,
            'user_behavior': 0.15,
            'popular': 0.10,
            'seasonal': 0.05
        }
        
        # Get recommendations from each strategy
        for strategy, weight in strategies_weights.items():
            try:
                strategy_recs = self.strategies[strategy](
                    user, product, limit * 2, exclude_owned, store_id
                )
                
                for rec in strategy_recs:
                    product_id = rec['product_id']
                    if product_id not in recommendations:
                        recommendations[product_id] = {
                            'product_id': product_id,
                            'product': rec['product'],
                            'score': 0,
                            'reasons': []
                        }
                    
                    recommendations[product_id]['score'] += rec['score'] * weight
                    recommendations[product_id]['reasons'].extend(rec.get('reasons', []))
                    
            except Exception as e:
                logger.error(f"Error in {strategy} strategy: {str(e)}")
                continue
        
        # Sort by score and return top recommendations
        sorted_recs = sorted(
            recommendations.values(),
            key=lambda x: x['score'],
            reverse=True
        )[:limit]
        
        return sorted_recs
    
    def _collaborative_filtering(
        self, 
        user: User = None, 
        product: Product = None,
        limit: int = 10,
        exclude_owned: bool = True,
        store_id: int = None
    ) -> List[Dict[str, Any]]:
        """
        Collaborative filtering based on user behavior similarities
        """
        if not user:
            return self._popular_products(user, product, limit, exclude_owned, store_id)
        
        try:
            # Get user's order history
            user_orders = Order.objects.filter(
                customer=user,
                status='DELIVERED'
            ).values_list('id', flat=True)
            
            if not user_orders:
                return self._trending_products(user, product, limit, exclude_owned, store_id)
            
            # Get products user has bought
            user_products = OrderItem.objects.filter(
                order__in=user_orders
            ).values_list('product_id', flat=True)
            
            # Find similar users who bought same products
            similar_users = User.objects.filter(
                orders__items__product_id__in=user_products,
                orders__status='DELIVERED'
            ).exclude(id=user.id).annotate(
                common_products=Count('orders__items__product_id', distinct=True)
            ).filter(common_products__gte=2).order_by('-common_products')[:50]
            
            # Get products bought by similar users
            recommended_products = Product.objects.filter(
                orderitem__order__customer__in=similar_users,
                orderitem__order__status='DELIVERED'
            ).exclude(
                id__in=user_products
            ).annotate(
                recommendation_score=Count('orderitem', distinct=True)
            ).order_by('-recommendation_score')
            
            if store_id:
                recommended_products = recommended_products.filter(store_id=store_id)
            
            return self._format_recommendations(
                recommended_products[:limit],
                ['کاربران با سلیقه مشابه این محصول را خریده‌اند']
            )
            
        except Exception as e:
            logger.error(f"Collaborative filtering error: {str(e)}")
            return self._popular_products(user, product, limit, exclude_owned, store_id)
    
    def _content_based_filtering(
        self, 
        user: User = None, 
        product: Product = None,
        limit: int = 10,
        exclude_owned: bool = True,
        store_id: int = None
    ) -> List[Dict[str, Any]]:
        """
        Content-based filtering using product attributes
        """
        base_products = []
        
        if product:
            base_products = [product]
        elif user:
            # Get user's recently viewed or purchased products
            user_orders = Order.objects.filter(
                customer=user,
                status='DELIVERED'
            ).order_by('-created_at')[:5]
            
            base_products = Product.objects.filter(
                orderitem__order__in=user_orders
            ).distinct()[:3]
        
        if not base_products:
            return self._trending_products(user, product, limit, exclude_owned, store_id)
        
        recommendations = set()
        
        for base_product in base_products:
            # Find products in same category
            similar_products = Product.objects.filter(
                category=base_product.category,
                is_active=True
            ).exclude(id=base_product.id)
            
            if store_id:
                similar_products = similar_products.filter(store_id=store_id)
            
            # Add products with similar price range
            price_range = base_product.price * 0.3  # 30% price variance
            price_similar = Product.objects.filter(
                price__gte=base_product.price - price_range,
                price__lte=base_product.price + price_range,
                is_active=True
            ).exclude(id=base_product.id)
            
            if store_id:
                price_similar = price_similar.filter(store_id=store_id)
            
            recommendations.update(similar_products[:limit//2])
            recommendations.update(price_similar[:limit//2])
        
        return self._format_recommendations(
            list(recommendations)[:limit],
            ['بر اساس علاقه‌مندی‌های شما']
        )
    
    def _trending_products(
        self, 
        user: User = None, 
        product: Product = None,
        limit: int = 10,
        exclude_owned: bool = True,
        store_id: int = None
    ) -> List[Dict[str, Any]]:
        """
        Get trending products based on recent views and purchases
        """
        # Products trending in last 7 days
        week_ago = timezone.now() - timedelta(days=7)
        
        trending = Product.objects.filter(
            is_active=True,
            created_at__gte=week_ago - timedelta(days=30)  # Not too old products
        ).annotate(
            view_count=Count('productview', filter=Q(productview__created_at__gte=week_ago)),
            order_count=Count('orderitem', filter=Q(orderitem__order__created_at__gte=week_ago)),
            trend_score=F('view_count') * 1 + F('order_count') * 3
        ).filter(
            trend_score__gt=0
        ).order_by('-trend_score')
        
        if store_id:
            trending = trending.filter(store_id=store_id)
        
        return self._format_recommendations(
            trending[:limit],
            ['محصولات پرطرفدار هفته']
        )
    
    def _popular_products(
        self, 
        user: User = None, 
        product: Product = None,
        limit: int = 10,
        exclude_owned: bool = True,
        store_id: int = None
    ) -> List[Dict[str, Any]]:
        """
        Get most popular products overall
        """
        popular = Product.objects.filter(
            is_active=True
        ).annotate(
            total_orders=Count('orderitem'),
            avg_rating=Avg('customer_reviews__rating'),
            popularity_score=F('total_orders') * 2 + F('avg_rating') * 10
        ).filter(
            total_orders__gt=0
        ).order_by('-popularity_score')
        
        if store_id:
            popular = popular.filter(store_id=store_id)
        
        return self._format_recommendations(
            popular[:limit],
            ['محصولات محبوب']
        )
    
    def _seasonal_recommendations(
        self, 
        user: User = None, 
        product: Product = None,
        limit: int = 10,
        exclude_owned: bool = True,
        store_id: int = None
    ) -> List[Dict[str, Any]]:
        """
        Get seasonal product recommendations based on Persian calendar
        """
        current_month = timezone.now().month
        
        # Define seasonal categories
        seasonal_keywords = {
            # Spring months (March-May)
            3: ['بهاری', 'نوروز', 'تعطیلات'],
            4: ['بهاری', 'پیک‌نیک', 'سفر'],
            5: ['بهاری', 'طبیعت‌گردی'],
            
            # Summer months (June-August)
            6: ['تابستانی', 'ساحلی', 'آفتابی'],
            7: ['تابستانی', 'تعطیلات', 'مسافرت'],
            8: ['تابستانی', 'ورزشی'],
            
            # Autumn months (September-November)
            9: ['پاییزی', 'مدرسه', 'بازگشت'],
            10: ['پاییزی', 'کار', 'اداری'],
            11: ['پاییزی', 'گرم'],
            
            # Winter months (December-February)
            12: ['زمستانی', 'گرم', 'یلدا'],
            1: ['زمستانی', 'سرد', 'داخلی'],
            2: ['زمستانی', 'هدیه']
        }
        
        keywords = seasonal_keywords.get(current_month, [])
        
        if keywords:
            seasonal = Product.objects.filter(
                Q(name__icontains=keywords[0]) | 
                Q(description__icontains=keywords[0]) |
                (Q(name__icontains=keywords[1]) | Q(description__icontains=keywords[1])) if len(keywords) > 1 else Q(),
                is_active=True
            ).order_by('-created_at')
            
            if store_id:
                seasonal = seasonal.filter(store_id=store_id)
            
            return self._format_recommendations(
                seasonal[:limit],
                [f'مناسب برای فصل جاری']
            )
        
        return self._trending_products(user, product, limit, exclude_owned, store_id)
    
    def _price_based_recommendations(
        self, 
        user: User = None, 
        product: Product = None,
        limit: int = 10,
        exclude_owned: bool = True,
        store_id: int = None
    ) -> List[Dict[str, Any]]:
        """
        Price-based recommendations considering user's budget
        """
        if not user:
            return self._popular_products(user, product, limit, exclude_owned, store_id)
        
        # Calculate user's average spending
        user_orders = Order.objects.filter(
            customer=user,
            status='DELIVERED'
        ).aggregate(avg_amount=Avg('total_amount'))
        
        avg_spending = user_orders['avg_amount'] or 100000  # Default to 100K Toman
        
        # Find products within user's typical budget (±50%)
        min_price = avg_spending * 0.5
        max_price = avg_spending * 1.5
        
        budget_products = Product.objects.filter(
            price__gte=min_price,
            price__lte=max_price,
            is_active=True
        ).order_by('-created_at')
        
        if store_id:
            budget_products = budget_products.filter(store_id=store_id)
        
        return self._format_recommendations(
            budget_products[:limit],
            ['مناسب بودجه شما']
        )
    
    def _cross_sell_recommendations(
        self, 
        user: User = None, 
        product: Product = None,
        limit: int = 10,
        exclude_owned: bool = True,
        store_id: int = None
    ) -> List[Dict[str, Any]]:
        """
        Cross-sell recommendations based on frequently bought together
        """
        if not product:
            return self._popular_products(user, product, limit, exclude_owned, store_id)
        
        # Find products frequently bought with the base product
        related_orders = Order.objects.filter(
            items__product=product
        ).values_list('id', flat=True)
        
        cross_sell = Product.objects.filter(
            orderitem__order__in=related_orders
        ).exclude(
            id=product.id
        ).annotate(
            co_purchase_count=Count('orderitem')
        ).filter(
            co_purchase_count__gte=2
        ).order_by('-co_purchase_count')
        
        if store_id:
            cross_sell = cross_sell.filter(store_id=store_id)
        
        return self._format_recommendations(
            cross_sell[:limit],
            ['کاربران همراه این محصول خریده‌اند']
        )
    
    def _recently_viewed_similar(
        self, 
        user: User = None, 
        product: Product = None,
        limit: int = 10,
        exclude_owned: bool = True,
        store_id: int = None
    ) -> List[Dict[str, Any]]:
        """
        Recommendations based on recently viewed products
        """
        if not user:
            return self._trending_products(user, product, limit, exclude_owned, store_id)
        
        # Get recently viewed products
        recent_views = ProductView.objects.filter(
            user=user
        ).order_by('-created_at')[:10]
        
        viewed_categories = [view.product.category for view in recent_views]
        
        similar_products = Product.objects.filter(
            category__in=viewed_categories,
            is_active=True
        ).exclude(
            id__in=[view.product_id for view in recent_views]
        ).order_by('-created_at')
        
        if store_id:
            similar_products = similar_products.filter(store_id=store_id)
        
        return self._format_recommendations(
            similar_products[:limit],
            ['بر اساس محصولات بازدید شده']
        )
    
    def _category_trending(
        self, 
        user: User = None, 
        product: Product = None,
        limit: int = 10,
        exclude_owned: bool = True,
        store_id: int = None
    ) -> List[Dict[str, Any]]:
        """
        Trending products within specific categories
        """
        target_category = None
        
        if product:
            target_category = product.category
        elif user:
            # Get user's most purchased category
            user_categories = OrderItem.objects.filter(
                order__customer=user
            ).values('product__category').annotate(
                count=Count('product__category')
            ).order_by('-count').first()
            
            if user_categories:
                target_category = user_categories['product__category']
        
        if not target_category:
            return self._trending_products(user, product, limit, exclude_owned, store_id)
        
        week_ago = timezone.now() - timedelta(days=7)
        
        category_trending = Product.objects.filter(
            category=target_category,
            is_active=True
        ).annotate(
            recent_orders=Count('orderitem', filter=Q(orderitem__order__created_at__gte=week_ago))
        ).filter(
            recent_orders__gt=0
        ).order_by('-recent_orders')
        
        if store_id:
            category_trending = category_trending.filter(store_id=store_id)
        
        return self._format_recommendations(
            category_trending[:limit],
            [f'پرطرفدار در دسته {target_category.name if hasattr(target_category, "name") else "انتخابی"}']
        )
    
    def _user_behavior_based(
        self, 
        user: User = None, 
        product: Product = None,
        limit: int = 10,
        exclude_owned: bool = True,
        store_id: int = None
    ) -> List[Dict[str, Any]]:
        """
        Recommendations based on comprehensive user behavior analysis
        """
        if not user:
            return self._popular_products(user, product, limit, exclude_owned, store_id)
        
        try:
            profile = CustomerProfile.objects.get(user=user)
        except CustomerProfile.DoesNotExist:
            return self._popular_products(user, product, limit, exclude_owned, store_id)
        
        # Analyze user's shopping patterns
        user_orders = Order.objects.filter(customer=user, status='DELIVERED')
        
        # Get user's preferred price range
        price_stats = user_orders.aggregate(
            avg_price=Avg('total_amount'),
            min_price=Sum('total_amount').__class__(0),  # Placeholder
            max_price=Sum('total_amount').__class__(999999999)  # Placeholder
        )
        
        # Get user's preferred shopping time (day of week, time of day)
        # Get user's brand preferences
        # Get user's review patterns
        
        behavior_products = Product.objects.filter(
            price__gte=price_stats['avg_price'] * 0.7,
            price__lte=price_stats['avg_price'] * 1.3,
            is_active=True
        ).order_by('-created_at')
        
        if store_id:
            behavior_products = behavior_products.filter(store_id=store_id)
        
        return self._format_recommendations(
            behavior_products[:limit],
            ['بر اساس الگوی خرید شما']
        )
    
    def _format_recommendations(
        self, 
        products: List[Product], 
        reasons: List[str],
        base_score: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        Format products into recommendation structure
        """
        recommendations = []
        
        for i, product in enumerate(products):
            # Calculate score based on position and base score
            score = base_score * (1.0 - (i * 0.05))  # Decrease score by position
            
            rec = {
                'product_id': product.id,
                'product': {
                    'id': product.id,
                    'name': product.name,
                    'price': float(product.price),
                    'image': product.images.first().image.url if product.images.exists() else None,
                    'rating': product.customer_reviews.aggregate(avg=Avg('rating'))['avg'] or 0,
                    'is_available': product.instances.filter(stock_quantity__gt=0).exists()
                },
                'score': score,
                'reasons': reasons,
                'confidence': min(score, 1.0)
            }
            
            recommendations.append(rec)
        
        return recommendations
    
    def _fallback_recommendations(self, limit: int = 10, store_id: int = None) -> List[Dict[str, Any]]:
        """
        Fallback recommendations when other strategies fail
        """
        fallback = Product.objects.filter(
            is_active=True
        ).order_by('-created_at')
        
        if store_id:
            fallback = fallback.filter(store_id=store_id)
        
        return self._format_recommendations(
            fallback[:limit],
            ['پیشنهادات عمومی']
        )
    
    def get_recommendation_analytics(self, user: User) -> Dict[str, Any]:
        """
        Get analytics for recommendation performance
        """
        if not user:
            return {}
        
        # Track recommendation clicks, conversions, etc.
        analytics = {
            'total_recommendations_shown': 0,
            'total_clicks': 0,
            'total_conversions': 0,
            'click_through_rate': 0,
            'conversion_rate': 0,
            'top_strategies': [],
            'user_preferences': {}
        }
        
        return analytics
    
    def update_user_interaction(
        self, 
        user: User, 
        product_id: int, 
        interaction_type: str,
        recommendation_id: str = None
    ):
        """
        Update user interaction data for improving recommendations
        
        Args:
            user: User who interacted
            product_id: Product that was interacted with
            interaction_type: Type of interaction (view, click, purchase, etc.)
            recommendation_id: ID of the recommendation that led to this interaction
        """
        # Log interaction for future recommendation improvements
        logger.info(f"User {user.id} performed {interaction_type} on product {product_id}")
        
        # Update recommendation tracking
        # This could be stored in a separate model for analytics
        
    def _get_persian_season(self, month: int) -> str:
        """
        Get Persian season name for given month
        """
        if month in [3, 4, 5]:
            return 'بهار'
        elif month in [6, 7, 8]:
            return 'تابستان'
        elif month in [9, 10, 11]:
            return 'پاییز'
        else:
            return 'زمستان'


# Singleton instance
recommendation_engine = ProductRecommendationEngine()
