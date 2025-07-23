from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.db import connection
from django.conf import settings
import logging

from .homepage_models import ContactRequest, PlatformSettings, Newsletter, FAQ
from .homepage_serializers import (
    ContactRequestSerializer, PlatformSettingsSerializer, 
    NewsletterSerializer, FAQSerializer, PlatformStatsSerializer,
    HealthCheckSerializer
)

logger = logging.getLogger(__name__)


class ContactRequestCreateView(generics.CreateAPIView):
    """Create contact request from homepage form"""
    queryset = ContactRequest.objects.all()
    serializer_class = ContactRequestSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        """Handle contact form submission"""
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            try:
                contact_request = serializer.save()
                
                # Log successful submission
                logger.info(f"Contact request created: {contact_request.name} - {contact_request.phone}")
                
                # TODO: Send notification email to admin
                # TODO: Send confirmation SMS to user
                
                return Response({
                    'success': True,
                    'message': 'درخواست شما با موفقیت ثبت شد. کارشناسان ما در اسرع وقت با شما تماس خواهند گرفت.',
                    'contact_id': str(contact_request.id)
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                logger.error(f"Error creating contact request: {str(e)}")
                return Response({
                    'success': False,
                    'message': 'خطایی در ثبت درخواست رخ داد. لطفاً مجدداً تلاش کنید.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False,
            'message': 'اطلاعات وارد شده صحیح نیست.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class PlatformSettingsView(generics.RetrieveAPIView):
    """Get platform settings for homepage"""
    serializer_class = PlatformSettingsSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_object(self):
        return PlatformSettings.get_settings()


class PlatformStatsView(APIView):
    """Get platform statistics for homepage"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """Return formatted platform statistics"""
        try:
            settings_obj = PlatformSettings.get_settings()
            
            stats_data = {
                'active_stores': settings_obj.active_stores_count,
                'daily_sales': settings_obj.daily_sales_amount,
                'customer_satisfaction': settings_obj.customer_satisfaction,
                'years_experience': settings_obj.years_experience
            }
            
            serializer = PlatformStatsSerializer(stats_data)
            return Response({
                'success': True,
                'stats': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error fetching platform stats: {str(e)}")
            return Response({
                'success': False,
                'message': 'خطا در دریافت آمار پلتفرم'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NewsletterSubscribeView(generics.CreateAPIView):
    """Subscribe to newsletter"""
    queryset = Newsletter.objects.all()
    serializer_class = NewsletterSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        """Handle newsletter subscription"""
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            try:
                subscription = serializer.save()
                
                logger.info(f"Newsletter subscription: {subscription.email}")
                
                return Response({
                    'success': True,
                    'message': 'با موفقیت در خبرنامه ثبت نام شدید.'
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                logger.error(f"Error creating newsletter subscription: {str(e)}")
                return Response({
                    'success': False,
                    'message': 'خطایی در ثبت نام رخ داد.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False,
            'message': 'ایمیل وارد شده صحیح نیست.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class FAQListView(generics.ListAPIView):
    """List frequently asked questions"""
    queryset = FAQ.objects.filter(is_active=True)
    serializer_class = FAQSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        """Filter by category if provided"""
        queryset = super().get_queryset()
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        return queryset


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """Health check endpoint"""
    try:
        # Test database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_status = "OK"
    except Exception:
        db_status = "ERROR"
    
    health_data = {
        'status': 'OK' if db_status == 'OK' else 'ERROR',
        'timestamp': timezone.now(),
        'version': getattr(settings, 'VERSION', '1.0.0'),
        'database': db_status
    }
    
    serializer = HealthCheckSerializer(health_data)
    
    response_status = status.HTTP_200_OK if db_status == 'OK' else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(serializer.data, status=response_status)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def homepage_data(request):
    """Get all homepage data in single request"""
    try:
        # Get platform settings
        settings_obj = PlatformSettings.get_settings()
        settings_data = PlatformSettingsSerializer(settings_obj).data
        
        # Get platform stats
        stats_data = {
            'active_stores': settings_obj.active_stores_count,
            'daily_sales': settings_obj.daily_sales_amount,
            'customer_satisfaction': settings_obj.customer_satisfaction,
            'years_experience': settings_obj.years_experience
        }
        stats_formatted = PlatformStatsSerializer(stats_data).data
        
        # Get FAQs
        faqs = FAQ.objects.filter(is_active=True)[:10]  # Limit to 10 most recent
        faqs_data = FAQSerializer(faqs, many=True).data
        
        return Response({
            'success': True,
            'data': {
                'settings': settings_data,
                'stats': stats_formatted,
                'faqs': faqs_data,
                'features': [
                    {
                        'title': 'فروشگاه آنلاین حرفه‌ای',
                        'description': 'با چند کلیک فروشگاه آنلاین خود را راه‌اندازی کنید',
                        'icon': 'store'
                    },
                    {
                        'title': 'مدیریت محصولات پیشرفته',
                        'description': 'سیستم مدیریت محصولات با ویژگی‌های کامل',
                        'icon': 'inventory'
                    },
                    {
                        'title': 'پرداخت‌های امن',
                        'description': 'اتصال به درگاه‌های پرداخت معتبر ایرانی',
                        'icon': 'payment'
                    },
                    {
                        'title': 'ارسال و لجستیک',
                        'description': 'اتصال به شرکت‌های حمل و نقل معتبر',
                        'icon': 'local_shipping'
                    }
                ]
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching homepage data: {str(e)}")
        return Response({
            'success': False,
            'message': 'خطا در دریافت اطلاعات صفحه اصلی'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def quick_contact(request):
    """Quick contact form for simple inquiries"""
    name = request.data.get('name', '').strip()
    phone = request.data.get('phone', '').strip()
    message = request.data.get('message', '').strip()
    
    if not name or not phone:
        return Response({
            'success': False,
            'message': 'نام و شماره تلفن الزامی است.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Create a simplified contact request
        contact_data = {
            'name': name,
            'phone': phone,
            'business_type': 'other',
            'message': message or 'تماس سریع از طریق فرم'
        }
        
        serializer = ContactRequestSerializer(data=contact_data, context={'request': request})
        if serializer.is_valid():
            contact_request = serializer.save()
            
            return Response({
                'success': True,
                'message': f'سلام {name}! درخواست شما ثبت شد. به زودی تماس می‌گیریم.'
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'message': 'اطلاعات وارد شده صحیح نیست.',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Error in quick contact: {str(e)}")
        return Response({
            'success': False,
            'message': 'خطایی رخ داد. لطفاً مجدداً تلاش کنید.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
