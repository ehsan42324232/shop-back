from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncDate
from datetime import datetime, timedelta
import logging

from .store_management_models import StoreRequest, StoreTheme, StoreSetting, StoreAnalytics
from .store_management_serializers import (
    StoreRequestSerializer, StoreRequestStatusSerializer,
    StoreThemeSerializer, StoreSettingSerializer, StoreAnalyticsSerializer,
    StoreBasicInfoSerializer, StoreDashboardSerializer, StoreCreationWizardSerializer
)
from .models import Store, Product
from .auth_models import PhoneUser
from .sms_service import send_welcome_sms

logger = logging.getLogger(__name__)


class CreateStoreRequestView(generics.CreateAPIView):
    """Create a new store request"""
    queryset = StoreRequest.objects.all()
    serializer_class = StoreRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        # Check if user already has a pending or approved request
        try:
            phone_user = PhoneUser.objects.get(user=request.user)
            
            existing_request = StoreRequest.objects.filter(
                user=phone_user,
                status__in=['pending', 'reviewing', 'approved']
            ).first()
            
            if existing_request:
                return Response({
                    'success': False,
                    'message': 'شما قبلاً درخواست ایجاد فروشگاه داده‌اید.',
                    'existing_request': StoreRequestStatusSerializer(existing_request).data
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except PhoneUser.DoesNotExist:
            return Response({
                'success': False,
                'message': 'کاربر معتبر نیست.'
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            try:
                store_request = serializer.save()
                
                logger.info(f"Store request created: {store_request.store_name} by {phone_user.get_full_name()}")
                
                return Response({
                    'success': True,
                    'message': 'درخواست شما با موفقیت ثبت شد. پس از بررسی، نتیجه از طریق پیامک اطلاع‌رسانی خواهد شد.',
                    'request': StoreRequestStatusSerializer(store_request).data
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                logger.error(f"Error creating store request: {str(e)}")
                return Response({
                    'success': False,
                    'message': 'خطایی در ثبت درخواست رخ داد.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False,
            'message': 'اطلاعات وارد شده صحیح نیست.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class MyStoreRequestView(APIView):
    """Get current user's store request status"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            phone_user = PhoneUser.objects.get(user=request.user)
            store_request = StoreRequest.objects.filter(user=phone_user).order_by('-created_at').first()
            
            if store_request:
                return Response({
                    'success': True,
                    'request': StoreRequestStatusSerializer(store_request).data
                })
            else:
                return Response({
                    'success': False,
                    'message': 'درخواستی یافت نشد.'
                }, status=status.HTTP_404_NOT_FOUND)
                
        except PhoneUser.DoesNotExist:
            return Response({
                'success': False,
                'message': 'کاربر معتبر نیست.'
            }, status=status.HTTP_400_BAD_REQUEST)


class MyStoreView(APIView):
    """Get current user's store information"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            # Get user's store
            store = Store.objects.get(owner=request.user, is_active=True)
            serializer = StoreBasicInfoSerializer(store)
            
            return Response({
                'success': True,
                'store': serializer.data
            })
            
        except Store.DoesNotExist:
            return Response({
                'success': False,
                'message': 'فروشگاهی یافت نشد. لطفاً ابتدا درخواست ایجاد فروشگاه دهید.'
            }, status=status.HTTP_404_NOT_FOUND)


class StoreThemeView(generics.RetrieveUpdateAPIView):
    """Get and update store theme"""
    serializer_class = StoreThemeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        store = get_object_or_404(Store, owner=self.request.user, is_active=True)
        theme, created = StoreTheme.objects.get_or_create(store=store)
        return theme

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        if response.status_code == 200:
            return Response({
                'success': True,
                'message': 'قالب فروشگاه با موفقیت به‌روزرسانی شد.',
                'theme': response.data
            })
        return response


class StoreSettingView(generics.RetrieveUpdateAPIView):
    """Get and update store settings"""
    serializer_class = StoreSettingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        store = get_object_or_404(Store, owner=self.request.user, is_active=True)
        settings, created = StoreSetting.objects.get_or_create(store=store)
        return settings

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        if response.status_code == 200:
            return Response({
                'success': True,
                'message': 'تنظیمات فروشگاه با موفقیت به‌روزرسانی شد.',
                'settings': response.data
            })
        return response


class StoreDashboardView(APIView):
    """Get store dashboard data with analytics"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            store = Store.objects.get(owner=request.user, is_active=True)
            
            # Get date ranges
            today = timezone.now().date()
            month_start = today.replace(day=1)
            week_ago = today - timedelta(days=7)
            
            # Get analytics for today
            today_analytics = StoreAnalytics.objects.filter(
                store=store,
                date=today
            ).first()
            
            # Get analytics for this month
            month_analytics = StoreAnalytics.objects.filter(
                store=store,
                date__gte=month_start
            ).aggregate(
                visitors=Sum('unique_visitors'),
                orders=Sum('orders_count'),
                revenue=Sum('revenue')
            )
            
            # Get product stats
            product_stats = Product.objects.filter(store=store).aggregate(
                total=Count('id'),
                active=Count('id', filter=Q(is_active=True)),
                out_of_stock=Count('id', filter=Q(stock=0, track_inventory=True))
            )
            
            # Weekly sales chart data
            weekly_data = StoreAnalytics.objects.filter(
                store=store,
                date__gte=week_ago
            ).order_by('date').values('date', 'revenue', 'orders_count')
            
            dashboard_data = {
                'store': StoreBasicInfoSerializer(store).data,
                'today_visitors': today_analytics.unique_visitors if today_analytics else 0,
                'today_orders': today_analytics.orders_count if today_analytics else 0,
                'today_revenue': today_analytics.revenue if today_analytics else 0,
                'month_visitors': month_analytics['visitors'] or 0,
                'month_orders': month_analytics['orders'] or 0,
                'month_revenue': month_analytics['revenue'] or 0,
                'total_products': product_stats['total'] or 0,
                'active_products': product_stats['active'] or 0,
                'out_of_stock_products': product_stats['out_of_stock'] or 0,
                'recent_orders': [],  # TODO: Implement when order model is ready
                'weekly_sales_chart': list(weekly_data),
                'popular_products': []  # TODO: Implement popular products
            }
            
            return Response({
                'success': True,
                'dashboard': dashboard_data
            })
            
        except Store.DoesNotExist:
            return Response({
                'success': False,
                'message': 'فروشگاهی یافت نشد.'
            }, status=status.HTTP_404_NOT_FOUND)


class StoreAnalyticsView(APIView):
    """Get store analytics for specific date range"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            store = Store.objects.get(owner=request.user, is_active=True)
            
            # Get date range from query params
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            
            if not start_date or not end_date:
                # Default to last 30 days
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=30)
            else:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            analytics = StoreAnalytics.objects.filter(
                store=store,
                date__range=[start_date, end_date]
            ).order_by('date')
            
            serializer = StoreAnalyticsSerializer(analytics, many=True)
            
            # Calculate summary
            summary = analytics.aggregate(
                total_visitors=Sum('unique_visitors'),
                total_orders=Sum('orders_count'),
                total_revenue=Sum('revenue'),
                avg_conversion_rate=Sum('conversion_rate') / analytics.count() if analytics.count() > 0 else 0
            )
            
            return Response({
                'success': True,
                'analytics': serializer.data,
                'summary': summary,
                'date_range': {
                    'start_date': start_date,
                    'end_date': end_date
                }
            })
            
        except Store.DoesNotExist:
            return Response({
                'success': False,
                'message': 'فروشگاهی یافت نشد.'
            }, status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            return Response({
                'success': False,
                'message': 'فرمت تاریخ صحیح نیست. از فرمت YYYY-MM-DD استفاده کنید.'
            }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def check_subdomain_availability(request):
    """Check if subdomain is available"""
    subdomain = request.data.get('subdomain', '').strip().lower()
    
    if not subdomain:
        return Response({
            'success': False,
            'message': 'زیردامنه الزامی است.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Clean subdomain
    from django.utils.text import slugify
    clean_subdomain = slugify(subdomain).replace('-', '')
    
    if len(clean_subdomain) < 3:
        return Response({
            'available': False,
            'message': 'زیردامنه باید حداقل 3 کاراکتر باشد.'
        })
    
    # Check availability
    if StoreRequest.objects.filter(subdomain=clean_subdomain).exists():
        return Response({
            'available': False,
            'message': 'این زیردامنه قبلاً رزرو شده است.'
        })
    
    if Store.objects.filter(domain__icontains=clean_subdomain).exists():
        return Response({
            'available': False,
            'message': 'این زیردامنه قبلاً استفاده شده است.'
        })
    
    # Reserved subdomains
    reserved = ['www', 'api', 'admin', 'mail', 'ftp', 'shop', 'store', 'mall', 'support']
    if clean_subdomain in reserved:
        return Response({
            'available': False,
            'message': 'این زیردامنه رزرو شده است.'
        })
    
    return Response({
        'available': True,
        'subdomain': clean_subdomain,
        'message': 'این زیردامنه در دسترس است.'
    })


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def store_creation_wizard_data(request):
    """Get data needed for store creation wizard"""
    return Response({
        'success': True,
        'data': {
            'business_types': [
                {'value': choice[0], 'label': choice[1]} 
                for choice in StoreRequest.BUSINESS_TYPE_CHOICES
            ],
            'monthly_estimates': [
                {'value': 'under_10m', 'label': 'کمتر از 10 میلیون تومان'},
                {'value': '10m_50m', 'label': '10 تا 50 میلیون تومان'},
                {'value': '50m_100m', 'label': '50 تا 100 میلیون تومان'},
                {'value': '100m_500m', 'label': '100 تا 500 میلیون تومان'},
                {'value': 'over_500m', 'label': 'بیش از 500 میلیون تومان'},
            ],
            'required_documents': [
                'کد ملی صاحب کسب‌وکار',
                'آدرس کسب‌وکار',
                'شماره تماس'
            ],
            'optional_documents': [
                'پروانه کسب',
                'وب‌سایت فعلی'
            ]
        }
    })
