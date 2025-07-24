from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from .recommendation_engine import recommendation_engine
from .models import Product, Order
from .serializers import ProductSerializer


class RecommendationViewSet(viewsets.ViewSet):
    """
    API endpoints for product recommendations
    """
    
    def get_permissions(self):
        """
        Set permissions based on action
        """
        if self.action in ['get_recommendations', 'get_user_recommendations']:
            return [IsAuthenticated()]
        return []
    
    @action(detail=False, methods=['get'])
    def get_recommendations(self, request):
        """
        Get personalized recommendations for authenticated user
        """
        try:
            user = request.user
            strategy = request.query_params.get('strategy', 'hybrid')
            limit = int(request.query_params.get('limit', 10))
            store_id = request.query_params.get('store_id')
            
            recommendations = recommendation_engine.get_recommendations(
                user=user,
                strategy=strategy,
                limit=limit,
                store_id=int(store_id) if store_id else None
            )
            
            return Response({
                'success': True,
                'recommendations': recommendations,
                'strategy_used': strategy,
                'user_id': user.id
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f'خطا در دریافت پیشنهادات: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])  
    def get_product_recommendations(self, request):
        """
        Get recommendations based on a specific product
        """
        try:
            product_id = request.query_params.get('product_id')
            if not product_id:
                return Response({
                    'success': False,
                    'error': 'شناسه محصول الزامی است'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'محصول یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
            
            strategy = request.query_params.get('strategy', 'content_based')
            limit = int(request.query_params.get('limit', 8))
            store_id = request.query_params.get('store_id')
            
            user = request.user if request.user.is_authenticated else None
            
            recommendations = recommendation_engine.get_recommendations(
                user=user,
                product=product,
                strategy=strategy,
                limit=limit,
                store_id=int(store_id) if store_id else None
            )
            
            return Response({
                'success': True,
                'recommendations': recommendations,
                'base_product': {
                    'id': product.id,
                    'name': product.name,
                    'price': float(product.price)
                },
                'strategy_used': strategy
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f'خطا در دریافت پیشنهادات محصول: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def get_trending_products(self, request):
        """
        Get trending products
        """
        try:
            limit = int(request.query_params.get('limit', 12))
            store_id = request.query_params.get('store_id')
            
            recommendations = recommendation_engine.get_recommendations(
                strategy='trending',
                limit=limit,
                store_id=int(store_id) if store_id else None
            )
            
            return Response({
                'success': True,
                'trending_products': recommendations,
                'generated_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f'خطا در دریافت محصولات پرطرفدار: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def get_popular_products(self, request):
        """
        Get most popular products
        """
        try:
            limit = int(request.query_params.get('limit', 12))
            store_id = request.query_params.get('store_id')
            
            recommendations = recommendation_engine.get_recommendations(
                strategy='popular',
                limit=limit,
                store_id=int(store_id) if store_id else None
            )
            
            return Response({
                'success': True,
                'popular_products': recommendations
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f'خطا در دریافت محصولات محبوب: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def get_seasonal_recommendations(self, request):
        """
        Get seasonal product recommendations
        """
        try:
            limit = int(request.query_params.get('limit', 10))
            store_id = request.query_params.get('store_id')
            user = request.user if request.user.is_authenticated else None
            
            recommendations = recommendation_engine.get_recommendations(
                user=user,
                strategy='seasonal',
                limit=limit,
                store_id=int(store_id) if store_id else None
            )
            
            # Get current Persian season
            from jdatetime import datetime as jdatetime
            persian_now = jdatetime.now()
            current_month = persian_now.month
            
            season_names = {
                1: 'بهار', 2: 'بهار', 3: 'بهار',
                4: 'تابستان', 5: 'تابستان', 6: 'تابستان',
                7: 'پاییز', 8: 'پاییز', 9: 'پاییز',
                10: 'زمستان', 11: 'زمستان', 12: 'زمستان'
            }
            
            current_season = season_names.get(current_month, 'بهار')
            
            return Response({
                'success': True,
                'seasonal_recommendations': recommendations,
                'current_season': current_season,
                'persian_month': current_month
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f'خطا در دریافت پیشنهادات فصلی: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def get_cross_sell_recommendations(self, request):
        """
        Get cross-sell recommendations for a product
        """
        try:
            product_id = request.query_params.get('product_id')
            if not product_id:
                return Response({
                    'success': False,
                    'error': 'شناسه محصول الزامی است'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'محصول یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
            
            limit = int(request.query_params.get('limit', 6))
            store_id = request.query_params.get('store_id')
            user = request.user if request.user.is_authenticated else None
            
            recommendations = recommendation_engine.get_recommendations(
                user=user,
                product=product,
                strategy='cross_sell',
                limit=limit,
                store_id=int(store_id) if store_id else None
            )
            
            return Response({
                'success': True,
                'cross_sell_recommendations': recommendations,
                'base_product_id': product.id
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f'خطا در دریافت پیشنهادات متقابل: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def track_interaction(self, request):
        """
        Track user interaction for improving recommendations
        """
        try:
            product_id = request.data.get('product_id')
            interaction_type = request.data.get('interaction_type')  # view, click, purchase, etc.
            recommendation_id = request.data.get('recommendation_id')
            
            if not product_id or not interaction_type:
                return Response({
                    'success': False,
                    'error': 'شناسه محصول و نوع تعامل الزامی است'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user = request.user if request.user.is_authenticated else None
            
            if user:
                recommendation_engine.update_user_interaction(
                    user=user,
                    product_id=int(product_id),
                    interaction_type=interaction_type,
                    recommendation_id=recommendation_id
                )
            
            return Response({
                'success': True,
                'message': 'تعامل کاربر ثبت شد'
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f'خطا در ثبت تعامل: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def get_recommendation_analytics(self, request):
        """
        Get recommendation analytics for authenticated user
        """
        try:
            user = request.user
            
            analytics = recommendation_engine.get_recommendation_analytics(user)
            
            return Response({
                'success': True,
                'analytics': analytics,
                'user_id': user.id
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f'خطا در دریافت آمار پیشنهادات: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def get_category_recommendations(self, request):
        """
        Get recommendations for a specific category
        """
        try:
            category_id = request.query_params.get('category_id')
            if not category_id:
                return Response({
                    'success': False,
                    'error': 'شناسه دسته‌بندی الزامی است'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            limit = int(request.query_params.get('limit', 10))
            store_id = request.query_params.get('store_id')
            user = request.user if request.user.is_authenticated else None
            
            # Get trending products in category
            recommendations = recommendation_engine.get_recommendations(
                user=user,
                strategy='category_trending',
                limit=limit,
                store_id=int(store_id) if store_id else None
            )
            
            return Response({
                'success': True,
                'category_recommendations': recommendations,
                'category_id': category_id
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f'خطا در دریافت پیشنهادات دسته‌بندی: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def get_price_based_recommendations(self, request):
        """
        Get recommendations based on user's price preferences
        """
        try:
            user = request.user
            limit = int(request.query_params.get('limit', 10))
            store_id = request.query_params.get('store_id')
            
            recommendations = recommendation_engine.get_recommendations(
                user=user,
                strategy='price_based',
                limit=limit,
                store_id=int(store_id) if store_id else None
            )
            
            return Response({
                'success': True,
                'price_based_recommendations': recommendations,
                'user_id': user.id
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f'خطا در دریافت پیشنهادات قیمتی: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def get_recently_viewed_similar(self, request):
        """
        Get recommendations based on recently viewed products
        """
        try:
            user = request.user
            limit = int(request.query_params.get('limit', 8))
            store_id = request.query_params.get('store_id')
            
            recommendations = recommendation_engine.get_recommendations(
                user=user,
                strategy='recently_viewed',
                limit=limit,
                store_id=int(store_id) if store_id else None
            )
            
            return Response({
                'success': True,
                'recently_viewed_similar': recommendations,
                'user_id': user.id
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f'خطا در دریافت پیشنهادات مشابه: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
