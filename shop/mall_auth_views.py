import random
import string
from datetime import datetime, timedelta
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
import json
import re
from .sms_service import SMSService
from .models import Store
import logging

logger = logging.getLogger(__name__)

class MallOTPService:
    """OTP Service specifically for Mall platform with Iranian mobile validation"""
    
    @staticmethod
    def validate_iranian_mobile(phone_number):
        """Validate Iranian mobile number format"""
        # Remove all non-digit characters
        cleaned = re.sub(r'\D', '', phone_number)
        
        # Check for Iranian mobile patterns
        patterns = [
            r'^09\d{9}$',           # 09xxxxxxxxx
            r'^9\d{9}$',            # 9xxxxxxxxx
            r'^00989\d{9}$',        # 00989xxxxxxxxx
            r'^98\d{10}$',          # 98xxxxxxxxx
        ]
        
        for pattern in patterns:
            if re.match(pattern, cleaned):
                # Normalize to 09xxxxxxxxx format
                if cleaned.startswith('00989'):
                    return '0' + cleaned[4:]
                elif cleaned.startswith('989'):
                    return '0' + cleaned[3:]
                elif cleaned.startswith('98'):
                    return '0' + cleaned[2:]
                elif cleaned.startswith('9') and len(cleaned) == 10:
                    return '0' + cleaned
                elif cleaned.startswith('09'):
                    return cleaned
                    
        raise ValidationError("شماره موبایل وارد شده معتبر نیست. لطفاً شماره ایرانی وارد کنید.")
    
    @staticmethod
    def generate_otp():
        """Generate 6-digit OTP"""
        return ''.join(random.choices(string.digits, k=6))
    
    @staticmethod
    def send_otp(phone_number, otp_code):
        """Send OTP via SMS service"""
        try:
            sms_service = SMSService()
            message = f"کد تایید ورود به پلتفرم مال: {otp_code}\nاین کد تا ۲ دقیقه معتبر است."
            
            result = sms_service.send_sms(
                phone_number=phone_number,
                message=message,
                template_name='otp_login'
            )
            
            return result
        except Exception as e:
            logger.error(f"Failed to send OTP to {phone_number}: {str(e)}")
            raise Exception("خطا در ارسال کد تایید. لطفاً دوباره تلاش کنید.")
    
    @staticmethod
    def store_otp(phone_number, otp_code):
        """Store OTP in cache with 2-minute expiration"""
        cache_key = f"mall_otp_{phone_number}"
        cache.set(cache_key, {
            'code': otp_code,
            'attempts': 0,
            'created_at': datetime.now().isoformat()
        }, timeout=120)  # 2 minutes
    
    @staticmethod
    def verify_otp(phone_number, submitted_code):
        """Verify OTP code"""
        cache_key = f"mall_otp_{phone_number}"
        otp_data = cache.get(cache_key)
        
        if not otp_data:
            raise ValidationError("کد تایید منقضی شده یا معتبر نیست.")
        
        # Check attempts
        if otp_data['attempts'] >= 3:
            cache.delete(cache_key)
            raise ValidationError("تعداد تلاش‌های مجاز به پایان رسیده. لطفاً مجدداً درخواست کد دهید.")
        
        # Verify code
        if otp_data['code'] != submitted_code:
            otp_data['attempts'] += 1
            cache.set(cache_key, otp_data, timeout=120)
            remaining = 3 - otp_data['attempts']
            raise ValidationError(f"کد تایید اشتباه است. {remaining} تلاش باقی مانده.")
        
        # Success - remove from cache
        cache.delete(cache_key)
        return True

@method_decorator(csrf_exempt, name='dispatch')
class SendOTPView(View):
    """Send OTP for authentication"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            phone_number = data.get('phone_number', '').strip()
            
            if not phone_number:
                return JsonResponse({
                    'success': False,
                    'message': 'شماره موبایل الزامی است.'
                }, status=400)
            
            # Validate and normalize phone number
            try:
                normalized_phone = MallOTPService.validate_iranian_mobile(phone_number)
            except ValidationError as e:
                return JsonResponse({
                    'success': False,
                    'message': str(e)
                }, status=400)
            
            # Check rate limiting
            rate_limit_key = f"mall_otp_rate_limit_{normalized_phone}"
            recent_requests = cache.get(rate_limit_key, 0)
            
            if recent_requests >= 3:  # Max 3 requests per hour
                return JsonResponse({
                    'success': False,
                    'message': 'تعداد درخواست‌های شما بیش از حد مجاز است. لطفاً یک ساعت دیگر تلاش کنید.'
                }, status=429)
            
            # Generate and send OTP
            otp_code = MallOTPService.generate_otp()
            
            try:
                MallOTPService.send_otp(normalized_phone, otp_code)
                MallOTPService.store_otp(normalized_phone, otp_code)
                
                # Update rate limiting
                cache.set(rate_limit_key, recent_requests + 1, timeout=3600)  # 1 hour
                
                return JsonResponse({
                    'success': True,
                    'message': f'کد تایید به شماره {normalized_phone} ارسال شد.',
                    'phone_number': normalized_phone
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': str(e)
                }, status=500)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'فرمت درخواست نامعتبر است.'
            }, status=400)
        except Exception as e:
            logger.error(f"Error in SendOTPView: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'خطای سرور. لطفاً دوباره تلاش کنید.'
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class VerifyOTPView(View):
    """Verify OTP and authenticate user"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            phone_number = data.get('phone_number', '').strip()
            otp_code = data.get('otp_code', '').strip()
            
            if not phone_number or not otp_code:
                return JsonResponse({
                    'success': False,
                    'message': 'شماره موبایل و کد تایید الزامی است.'
                }, status=400)
            
            # Normalize phone number
            try:
                normalized_phone = MallOTPService.validate_iranian_mobile(phone_number)
            except ValidationError as e:
                return JsonResponse({
                    'success': False,
                    'message': str(e)
                }, status=400)
            
            # Verify OTP
            try:
                MallOTPService.verify_otp(normalized_phone, otp_code)
            except ValidationError as e:
                return JsonResponse({
                    'success': False,
                    'message': str(e)
                }, status=400)
            
            # Find or create user
            user = None
            created = False
            
            # Try to find user by phone number (stored in username field)
            try:
                user = User.objects.get(username=normalized_phone)
            except User.DoesNotExist:
                # Create new user
                user = User.objects.create_user(
                    username=normalized_phone,
                    first_name='کاربر',
                    last_name='مال',
                    is_active=True
                )
                created = True
                logger.info(f"New user created for phone: {normalized_phone}")
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token
            
            # Get user's stores
            user_stores = Store.objects.filter(owner=user).values(
                'id', 'name', 'domain', 'is_active', 'is_approved'
            )
            
            # Determine user role
            user_role = 'admin' if user.is_superuser else 'store_owner'
            if not user_stores.exists() and not user.is_superuser:
                user_role = 'customer'
            
            response_data = {
                'success': True,
                'message': 'ورود موفقیت‌آمیز بود.' if not created else 'حساب کاربری جدید ایجاد و ورود انجام شد.',
                'data': {
                    'user_id': user.id,
                    'username': user.username,
                    'name': f"{user.first_name} {user.last_name}".strip(),
                    'phone_number': normalized_phone,
                    'role': user_role,
                    'is_new_user': created,
                    'stores': list(user_stores),
                    'access_token': str(access_token),
                    'refresh_token': str(refresh),
                }
            }
            
            # If user has stores, add primary store info
            if user_stores.exists():
                primary_store = user_stores.first()
                response_data['data']['primary_store'] = primary_store
            
            return JsonResponse(response_data)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'فرمت درخواست نامعتبر است.'
            }, status=400)
        except Exception as e:
            logger.error(f"Error in VerifyOTPView: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'خطای سرور. لطفاً دوباره تلاش کنید.'
            }, status=500)

@api_view(['POST'])
@permission_classes([AllowAny])
def request_store_creation(request):
    """Handle store creation requests from homepage"""
    try:
        data = request.data
        
        required_fields = ['name', 'phone']
        for field in required_fields:
            if not data.get(field):
                return Response({
                    'success': False,
                    'message': f'فیلد {field} الزامی است.'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate phone number
        try:
            normalized_phone = MallOTPService.validate_iranian_mobile(data['phone'])
        except ValidationError as e:
            return Response({
                'success': False,
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Store request in cache or database for admin review
        request_data = {
            'name': data['name'],
            'phone': normalized_phone,
            'email': data.get('email', ''),
            'business_type': data.get('business_type', ''),
            'description': data.get('description', ''),
            'requested_at': datetime.now().isoformat(),
            'ip_address': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')
        }
        
        # Store in cache for admin review (or you could save to database)
        cache_key = f"mall_store_request_{normalized_phone}_{int(datetime.now().timestamp())}"
        cache.set(cache_key, request_data, timeout=86400 * 7)  # 7 days
        
        # TODO: Send notification to admin
        # TODO: Send confirmation SMS to user
        
        return Response({
            'success': True,
            'message': 'درخواست شما با موفقیت ثبت شد. تیم ما در اسرع وقت با شما تماس خواهد گرفت.',
            'request_id': cache_key
        })
        
    except Exception as e:
        logger.error(f"Error in request_store_creation: {str(e)}")
        return Response({
            'success': False,
            'message': 'خطای سرور. لطفاً دوباره تلاش کنید.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([AllowAny])
def platform_stats(request):
    """Get public platform statistics for homepage"""
    try:
        from django.db.models import Count, Q
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        
        stats = {
            'total_stores': Store.objects.filter(is_active=True, is_approved=True).count(),
            'total_products': 0,  # You'll need to implement this based on your Product model
            'active_stores_30d': Store.objects.filter(
                is_active=True, 
                is_approved=True,
                updated_at__gte=thirty_days_ago
            ).count(),
            'new_stores_30d': Store.objects.filter(
                is_approved=True,
                approved_at__gte=thirty_days_ago
            ).count(),
        }
        
        # Add product count if Product model is available
        try:
            from .models import Product
            stats['total_products'] = Product.objects.filter(
                store__is_active=True,
                store__is_approved=True,
                is_active=True
            ).count()
        except:
            stats['total_products'] = 0
        
        return Response({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        logger.error(f"Error in platform_stats: {str(e)}")
        return Response({
            'success': False,
            'message': 'خطا در دریافت آمار'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
