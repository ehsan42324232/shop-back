from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
import logging
import uuid

from .auth_models import OTPVerification, PhoneUser, LoginSession
from .auth_serializers import (
    SendOTPSerializer, VerifyOTPSerializer, RegisterUserSerializer,
    PhoneUserSerializer, LoginResponseSerializer, ChangePasswordSerializer,
    SessionSerializer
)
from .sms_service import send_otp_sms, send_verification_sms, send_welcome_sms

logger = logging.getLogger(__name__)


class SendOTPView(APIView):
    """Send OTP to phone number"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        
        if serializer.is_valid():
            phone = serializer.validated_data['phone']
            purpose = serializer.validated_data['purpose']
            
            try:
                # Get client IP
                ip_address = self.get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                
                # Check if user exists for login purpose
                if purpose == 'login':
                    if not PhoneUser.objects.filter(phone=phone).exists():
                        return Response({
                            'success': False,
                            'message': 'این شماره تلفن ثبت نشده است. لطفاً ابتدا ثبت نام کنید.'
                        }, status=status.HTTP_404_NOT_FOUND)
                
                # Check if user already exists for register purpose
                elif purpose == 'register':
                    if PhoneUser.objects.filter(phone=phone).exists():
                        return Response({
                            'success': False,
                            'message': 'این شماره تلفن قبلاً ثبت شده است. لطفاً وارد شوید.'
                        }, status=status.HTTP_400_BAD_REQUEST)
                
                # Invalidate previous OTPs
                OTPVerification.objects.filter(
                    phone=phone,
                    purpose=purpose,
                    is_verified=False
                ).update(is_verified=True)  # Mark as used
                
                # Create new OTP
                otp = OTPVerification.objects.create(
                    phone=phone,
                    purpose=purpose,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                
                # Send SMS
                success, message = send_otp_sms(phone, otp.otp_code, purpose)
                
                if success:
                    logger.info(f"OTP sent to {phone} for {purpose}")
                    return Response({
                        'success': True,
                        'message': 'کد تایید ارسال شد.',
                        'expires_in': 300,  # 5 minutes
                        'phone': phone
                    })
                else:
                    logger.error(f"Failed to send OTP to {phone}: {message}")
                    return Response({
                        'success': False,
                        'message': message
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    
            except Exception as e:
                logger.error(f"Error sending OTP: {str(e)}")
                return Response({
                    'success': False,
                    'message': 'خطایی در ارسال کد تایید رخ داد.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False,
            'message': 'اطلاعات وارد شده صحیح نیست.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class VerifyOTPView(APIView):
    """Verify OTP and login user"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        
        if serializer.is_valid():
            phone = serializer.validated_data['phone']
            otp_code = serializer.validated_data['otp_code']
            purpose = serializer.validated_data['purpose']
            
            try:
                # Find OTP
                otp = OTPVerification.objects.filter(
                    phone=phone,
                    purpose=purpose,
                    is_verified=False
                ).first()
                
                if not otp:
                    return Response({
                        'success': False,
                        'message': 'کد تایید یافت نشد یا منقضی شده است.'
                    }, status=status.HTTP_404_NOT_FOUND)
                
                # Verify OTP
                success, message = otp.verify(otp_code)
                
                if success:
                    # Handle different purposes
                    if purpose == 'login':
                        return self.handle_login(phone, request)
                    elif purpose == 'phone_verify':
                        return self.handle_phone_verification(phone)
                    else:
                        return Response({
                            'success': True,
                            'message': message
                        })
                else:
                    return Response({
                        'success': False,
                        'message': message
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Exception as e:
                logger.error(f"Error verifying OTP: {str(e)}")
                return Response({
                    'success': False,
                    'message': 'خطایی در تایید کد رخ داد.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False,
            'message': 'اطلاعات وارد شده صحیح نیست.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def handle_login(self, phone, request):
        """Handle user login after OTP verification"""
        try:
            phone_user = PhoneUser.objects.get(phone=phone)
            
            # Update last login
            phone_user.last_login_at = timezone.now()
            phone_user.save()
            
            # Create login session
            session = LoginSession.objects.create(
                user=phone_user,
                session_key=request.session.session_key or str(uuid.uuid4()),
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Login Django user
            login(request, phone_user.user)
            
            response_data = {
                'success': True,
                'message': f'خوش آمدید {phone_user.get_full_name()}',
                'user': PhoneUserSerializer(phone_user).data,
                'token': session.session_key,
                'expires_at': session.expires_at
            }
            
            return Response(response_data)
            
        except PhoneUser.DoesNotExist:
            return Response({
                'success': False,
                'message': 'کاربر یافت نشد.'
            }, status=status.HTTP_404_NOT_FOUND)

    def handle_phone_verification(self, phone):
        """Handle phone number verification"""
        try:
            phone_user = PhoneUser.objects.get(phone=phone)
            phone_user.verify_phone()
            
            # Send verification SMS
            send_verification_sms(phone, phone_user.get_full_name())
            
            return Response({
                'success': True,
                'message': 'شماره تلفن با موفقیت تایید شد.'
            })
            
        except PhoneUser.DoesNotExist:
            return Response({
                'success': False,
                'message': 'کاربر یافت نشد.'
            }, status=status.HTTP_404_NOT_FOUND)

    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class RegisterView(generics.CreateAPIView):
    """Register new user with OTP verification"""
    queryset = PhoneUser.objects.all()
    serializer_class = RegisterUserSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            try:
                phone_user = serializer.save()
                
                # Send welcome SMS
                send_welcome_sms(
                    phone_user.phone, 
                    phone_user.get_full_name()
                )
                
                # Auto-login after registration
                login(request, phone_user.user)
                
                # Create login session
                session = LoginSession.objects.create(
                    user=phone_user,
                    session_key=request.session.session_key or str(uuid.uuid4()),
                    ip_address=self.get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
                response_data = {
                    'success': True,
                    'message': f'خوش آمدید {phone_user.get_full_name()}! حساب شما با موفقیت ایجاد شد.',
                    'user': PhoneUserSerializer(phone_user).data,
                    'token': session.session_key,
                    'expires_at': session.expires_at
                }
                
                return Response(response_data, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                logger.error(f"Registration error: {str(e)}")
                return Response({
                    'success': False,
                    'message': 'خطایی در ثبت نام رخ داد.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False,
            'message': 'اطلاعات وارد شده صحیح نیست.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class LogoutView(APIView):
    """Logout user and invalidate session"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            # Get phone user
            phone_user = PhoneUser.objects.get(user=request.user)
            
            # Invalidate current session
            if hasattr(request, 'session'):
                LoginSession.objects.filter(
                    user=phone_user,
                    session_key=request.session.session_key
                ).update(is_active=False)
            
            # Django logout
            logout(request)
            
            return Response({
                'success': True,
                'message': 'با موفقیت خارج شدید.'
            })
            
        except PhoneUser.DoesNotExist:
            logout(request)
            return Response({
                'success': True,
                'message': 'خارج شدید.'
            })
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return Response({
                'success': False,
                'message': 'خطایی در خروج رخ داد.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProfileView(generics.RetrieveUpdateAPIView):
    """Get and update user profile"""
    serializer_class = PhoneUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return PhoneUser.objects.get(user=self.request.user)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def auth_status(request):
    """Check authentication status"""
    try:
        phone_user = PhoneUser.objects.get(user=request.user)
        return Response({
            'authenticated': True,
            'user': PhoneUserSerializer(phone_user).data
        })
    except PhoneUser.DoesNotExist:
        return Response({
            'authenticated': False,
            'user': None
        })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def change_password(request):
    """Change user password"""
    serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        user = request.user
        new_password = serializer.validated_data['new_password']
        
        user.set_password(new_password)
        user.save()
        
        return Response({
            'success': True,
            'message': 'رمز عبور با موفقیت تغییر کرد.'
        })
    
    return Response({
        'success': False,
        'message': 'خطا در تغییر رمز عبور.',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)
