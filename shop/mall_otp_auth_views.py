# Mall Platform OTP Authentication Views
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import MallUser, OTPVerification
from .otp_service import OTPService
from .serializers import MallUserSerializer
import re
import random
import string
from datetime import datetime, timedelta


class MallOTPAuthenticationViews:
    """OTP Authentication views for Mall platform"""
    
    @staticmethod
    def format_iranian_phone(phone):
        """Format Iranian phone number to international format"""
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)
        
        # Handle different Iranian phone number formats
        if digits.startswith('0'):
            # Convert 09xxxxxxxxx to +989xxxxxxxxx
            return '+98' + digits[1:]
        elif digits.startswith('98'):
            # Already in international format
            return '+' + digits
        elif digits.startswith('9') and len(digits) == 10:
            # 9xxxxxxxxx format
            return '+98' + digits
        elif len(digits) == 11 and digits.startswith('09'):
            # 09xxxxxxxxx format
            return '+98' + digits[1:]
        
        # Default: assume it needs +98 prefix
        return '+98' + digits
    
    @staticmethod
    def is_valid_iranian_phone(phone):
        """Validate Iranian phone number"""
        formatted = MallOTPAuthenticationViews.format_iranian_phone(phone)
        # Iranian mobile numbers: +989xxxxxxxxx (13 digits total)
        iranian_mobile_regex = r'^\+989[0-9]{9}$'
        return re.match(iranian_mobile_regex, formatted) is not None


@api_view(['POST'])
@permission_classes([AllowAny])
def request_otp(request):
    """Request OTP for phone number authentication"""
    try:
        phone = request.data.get('phone')
        
        if not phone:
            return Response({
                'success': False,
                'message': 'شماره تلفن الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Format and validate phone number
        formatted_phone = MallOTPAuthenticationViews.format_iranian_phone(phone)
        
        if not MallOTPAuthenticationViews.is_valid_iranian_phone(formatted_phone):
            return Response({
                'success': False,
                'message': 'شماره تلفن نامعتبر است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate OTP code
        otp_code = ''.join(random.choices(string.digits, k=5))
        
        # Save or update OTP verification record
        otp_verification, created = OTPVerification.objects.get_or_create(
            phone=formatted_phone,
            defaults={
                'code': otp_code,
                'expires_at': timezone.now() + timedelta(minutes=5),
                'attempts': 0
            }
        )
        
        if not created:
            # Update existing record
            otp_verification.code = otp_code
            otp_verification.expires_at = timezone.now() + timedelta(minutes=5)
            otp_verification.attempts = 0
            otp_verification.is_verified = False
            otp_verification.save()
        
        # Send OTP via SMS
        try:
            otp_service = OTPService()
            sms_sent = otp_service.send_otp_sms(formatted_phone, otp_code)
            
            if sms_sent:
                return Response({
                    'success': True,
                    'message': f'کد تایید به شماره {formatted_phone[-4:]}***{formatted_phone[:4]} ارسال شد'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': 'خطا در ارسال پیامک. لطفاً دوباره تلاش کنید'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            # In development, return the OTP code for testing
            if settings.DEBUG:
                return Response({
                    'success': True,
                    'message': f'کد تایید: {otp_code} (حالت توسعه)',
                    'debug_code': otp_code
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': 'خطا در ارسال پیامک'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطای سرور. لطفاً دوباره تلاش کنید'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_otp(request):
    """Verify OTP and authenticate user"""
    try:
        phone = request.data.get('phone')
        code = request.data.get('code')
        
        if not phone or not code:
            return Response({
                'success': False,
                'message': 'شماره تلفن و کد تایید الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Format phone number
        formatted_phone = MallOTPAuthenticationViews.format_iranian_phone(phone)
        
        # Find OTP verification record
        try:
            otp_verification = OTPVerification.objects.get(phone=formatted_phone)
        except OTPVerification.DoesNotExist:
            return Response({
                'success': False,
                'message': 'کد تایید یافت نشد. ابتدا درخواست کد جدید دهید'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if OTP is expired
        if otp_verification.expires_at < timezone.now():
            return Response({
                'success': False,
                'message': 'کد تایید منقضی شده است. کد جدید درخواست دهید'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if too many attempts
        if otp_verification.attempts >= 5:
            return Response({
                'success': False,
                'message': 'تعداد تلاش‌های نادرست زیاد است. کد جدید درخواست دهید'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify OTP code
        if otp_verification.code != code:
            otp_verification.attempts += 1
            otp_verification.save()
            
            remaining_attempts = 5 - otp_verification.attempts
            return Response({
                'success': False,
                'message': f'کد تایید نادرست است. {remaining_attempts} تلاش باقی‌مانده'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Mark OTP as verified
        otp_verification.is_verified = True
        otp_verification.save()
        
        # Find or create user
        try:
            mall_user = MallUser.objects.get(phone=formatted_phone)
            user = mall_user.user
        except MallUser.DoesNotExist:
            # Create new user account
            username = f"user_{formatted_phone[3:]}"  # Remove +98 prefix
            user = User.objects.create_user(
                username=username,
                first_name='کاربر',
                last_name='جدید'
            )
            
            mall_user = MallUser.objects.create(
                user=user,
                phone=formatted_phone,
                is_customer=True,
                is_active=True
            )
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        
        # Serialize user data
        user_serializer = MallUserSerializer(mall_user)
        
        return Response({
            'success': True,
            'message': 'ورود با موفقیت انجام شد',
            'user': user_serializer.data,
            'token': access_token,
            'refresh_token': str(refresh),
            'expires_in': settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطای سرور. لطفاً دوباره تلاش کنید'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def register_store_owner(request):
    """Register new store owner"""
    try:
        phone = request.data.get('phone')
        name = request.data.get('name')
        business_name = request.data.get('business_name')
        business_type = request.data.get('business_type', '')
        
        if not phone or not name or not business_name:
            return Response({
                'success': False,
                'message': 'شماره تلفن، نام و نام کسب‌وکار الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Format phone number
        formatted_phone = MallOTPAuthenticationViews.format_iranian_phone(phone)
        
        # Check if user already exists
        if MallUser.objects.filter(phone=formatted_phone).exists():
            return Response({
                'success': False,
                'message': 'کاربری با این شماره تلفن قبلاً ثبت نام کرده است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create Django user
        username = f"store_{formatted_phone[3:]}"
        user = User.objects.create_user(
            username=username,
            first_name=name.split()[0] if name.split() else name,
            last_name=' '.join(name.split()[1:]) if len(name.split()) > 1 else ''
        )
        
        # Create Mall user
        mall_user = MallUser.objects.create(
            user=user,
            phone=formatted_phone,
            business_name=business_name,
            business_type=business_type,
            is_store_owner=True,
            is_active=True
        )
        
        return Response({
            'success': True,
            'message': 'ثبت نام با موفقیت انجام شد. اکنون می‌توانید وارد شوید'
        }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطای سرور. لطفاً دوباره تلاش کنید'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def register_customer(request):
    """Register new customer"""
    try:
        phone = request.data.get('phone')
        name = request.data.get('name')
        email = request.data.get('email', '')
        
        if not phone or not name:
            return Response({
                'success': False,
                'message': 'شماره تلفن و نام الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Format phone number
        formatted_phone = MallOTPAuthenticationViews.format_iranian_phone(phone)
        
        # Check if user already exists
        if MallUser.objects.filter(phone=formatted_phone).exists():
            return Response({
                'success': False,
                'message': 'کاربری با این شماره تلفن قبلاً ثبت نام کرده است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create Django user
        username = f"customer_{formatted_phone[3:]}"
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=name.split()[0] if name.split() else name,
            last_name=' '.join(name.split()[1:]) if len(name.split()) > 1 else ''
        )
        
        # Create Mall user
        mall_user = MallUser.objects.create(
            user=user,
            phone=formatted_phone,
            is_customer=True,
            is_active=True
        )
        
        return Response({
            'success': True,
            'message': 'ثبت نام با موفقیت انجام شد. اکنون می‌توانید وارد شوید'
        }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطای سرور. لطفاً دوباره تلاش کنید'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_profile(request):
    """Get current user profile"""
    try:
        mall_user = MallUser.objects.get(user=request.user)
        serializer = MallUserSerializer(mall_user)
        
        return Response({
            'success': True,
            'user': serializer.data
        }, status=status.HTTP_200_OK)
    
    except MallUser.DoesNotExist:
        return Response({
            'success': False,
            'message': 'کاربر یافت نشد'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطای سرور'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """Update user profile"""
    try:
        mall_user = MallUser.objects.get(user=request.user)
        user = request.user
        
        # Update user fields
        name = request.data.get('name')
        if name:
            name_parts = name.split()
            user.first_name = name_parts[0] if name_parts else ''
            user.last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            user.save()
        
        # Update email if provided
        email = request.data.get('email')
        if email:
            user.email = email
            user.save()
        
        # Update Mall user fields
        business_name = request.data.get('business_name')
        if business_name and mall_user.is_store_owner:
            mall_user.business_name = business_name
        
        business_type = request.data.get('business_type')
        if business_type and mall_user.is_store_owner:
            mall_user.business_type = business_type
        
        mall_user.save()
        
        # Return updated user data
        serializer = MallUserSerializer(mall_user)
        
        return Response({
            'success': True,
            'message': 'پروفایل با موفقیت به‌روزرسانی شد',
            'user': serializer.data
        }, status=status.HTTP_200_OK)
    
    except MallUser.DoesNotExist:
        return Response({
            'success': False,
            'message': 'کاربر یافت نشد'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطای سرور'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def refresh_token(request):
    """Refresh JWT token"""
    try:
        refresh_token = request.data.get('refresh_token')
        
        if not refresh_token:
            return Response({
                'success': False,
                'message': 'توکن تجدید الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            refresh = RefreshToken(refresh_token)
            access_token = str(refresh.access_token)
            
            # Get user data
            mall_user = MallUser.objects.get(user=request.user)
            serializer = MallUserSerializer(mall_user)
            
            return Response({
                'success': True,
                'token': access_token,
                'user': serializer.data,
                'expires_in': settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': 'توکن نامعتبر است'
            }, status=status.HTTP_401_UNAUTHORIZED)
    
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطای سرور'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """Logout user"""
    try:
        refresh_token = request.data.get('refresh_token')
        
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass  # Token might already be invalid
        
        return Response({
            'success': True,
            'message': 'خروج با موفقیت انجام شد'
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({
            'success': False,
            'message': 'خطای سرور'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
