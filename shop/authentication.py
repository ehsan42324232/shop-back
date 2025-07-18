from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
import json


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    مثل رجیستر کردن کاربر جدید
    """
    try:
        data = json.loads(request.body) if isinstance(request.data, str) else request.data
        
        # اطلاعات مورد نیاز
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        phone = data.get('phone', '').strip()
        
        # اعتبارسنجی
        if not username:
            return Response({
                'error': 'نام کاربری الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not email:
            return Response({
                'error': 'ایمیل الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not password:
            return Response({
                'error': 'رمز عبور الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # چک کردن یکتا بودن نام کاربری و ایمیل
        if User.objects.filter(username=username).exists():
            return Response({
                'error': 'نام کاربری قبلاً استفاده شده است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if User.objects.filter(email=email).exists():
            return Response({
                'error': 'ایمیل قبلاً استفاده شده است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # اعتبارسنجی رمز عبور
        try:
            validate_password(password)
        except ValidationError as e:
            return Response({
                'error': 'رمز عبور ضعیف است: ' + ', '.join(e.messages)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # ایجاد کاربر جدید
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            # ایجاد توکن
            token, created = Token.objects.get_or_create(user=user)
            
        return Response({
            'message': 'کاربر با موفقیت ثبت شد',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'token': token.key
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'error': f'خطا در ثبت کاربر: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    ورود کاربر به سیستم
    """
    try:
        data = json.loads(request.body) if isinstance(request.data, str) else request.data
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return Response({
                'error': 'نام کاربری و رمز عبور الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # تلاش برای ورود با ایمیل یا نام کاربری
        user = authenticate(username=username, password=password)
        
        if not user:
            # تلاش با ایمیل
            try:
                user_obj = User.objects.get(email=username)
                user = authenticate(username=user_obj.username, password=password)
            except User.DoesNotExist:
                pass
        
        if user and user.is_active:
            token, created = Token.objects.get_or_create(user=user)
            
            # بررسی نقش کاربر
            is_platform_admin = user.is_superuser
            is_store_owner = user.stores.exists() if hasattr(user, 'stores') else False
            
            return Response({
                'message': 'ورود موفقیت‌آمیز',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_platform_admin': is_platform_admin,
                    'is_store_owner': is_store_owner,
                },
                'token': token.key
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'نام کاربری یا رمز عبور اشتباه است'
            }, status=status.HTTP_401_UNAUTHORIZED)
            
    except Exception as e:
        return Response({
            'error': f'خطا در ورود: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    خروج کاربر از سیستم
    """
    try:
        # حذف توکن کاربر
        token = Token.objects.get(user=request.user)
        token.delete()
        
        return Response({
            'message': 'خروج موفقیت‌آمیز'
        }, status=status.HTTP_200_OK)
        
    except Token.DoesNotExist:
        return Response({
            'message': 'خروج موفقیت‌آمیز'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': f'خطا در خروج: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile(request):
    """
    دریافت اطلاعات کاربر
    """
    try:
        user = request.user
        
        # بررسی نقش کاربر
        is_platform_admin = user.is_superuser
        is_store_owner = user.stores.exists() if hasattr(user, 'stores') else False
        
        # اطلاعات فروشگاه‌های کاربر
        stores = []
        if is_store_owner:
            for store in user.stores.all():
                stores.append({
                    'id': str(store.id),
                    'name': store.name,
                    'domain': store.domain,
                    'is_active': store.is_active,
                    'is_approved': store.is_approved,
                })
        
        return Response({
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_platform_admin': is_platform_admin,
                'is_store_owner': is_store_owner,
                'date_joined': user.date_joined,
                'last_login': user.last_login,
            },
            'stores': stores
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'خطا در دریافت اطلاعات: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """
    به‌روزرسانی اطلاعات کاربر
    """
    try:
        data = json.loads(request.body) if isinstance(request.data, str) else request.data
        user = request.user
        
        # به‌روزرسانی فیلدهای مجاز
        allowed_fields = ['first_name', 'last_name', 'email']
        
        for field in allowed_fields:
            if field in data:
                if field == 'email':
                    # چک کردن یکتا بودن ایمیل
                    if User.objects.filter(email=data[field]).exclude(id=user.id).exists():
                        return Response({
                            'error': 'ایمیل قبلاً استفاده شده است'
                        }, status=status.HTTP_400_BAD_REQUEST)
                
                setattr(user, field, data[field])
        
        user.save()
        
        return Response({
            'message': 'اطلاعات با موفقیت به‌روزرسانی شد',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'خطا در به‌روزرسانی: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    تغییر رمز عبور کاربر
    """
    try:
        data = json.loads(request.body) if isinstance(request.data, str) else request.data
        user = request.user
        
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        
        if not old_password or not new_password:
            return Response({
                'error': 'رمز عبور قدیم و جدید الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # بررسی رمز عبور قدیم
        if not user.check_password(old_password):
            return Response({
                'error': 'رمز عبور قدیم اشتباه است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # اعتبارسنجی رمز عبور جدید
        try:
            validate_password(new_password, user)
        except ValidationError as e:
            return Response({
                'error': 'رمز عبور جدید ضعیف است: ' + ', '.join(e.messages)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # تغییر رمز عبور
        user.set_password(new_password)
        user.save()
        
        # حذف توکن فعلی و ایجاد توکن جدید
        Token.objects.filter(user=user).delete()
        new_token = Token.objects.create(user=user)
        
        return Response({
            'message': 'رمز عبور با موفقیت تغییر یافت',
            'token': new_token.key
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'خطا در تغییر رمز عبور: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def request_store(request):
    """
    درخواست ایجاد فروشگاه جدید
    """
    try:
        data = json.loads(request.body) if isinstance(request.data, str) else request.data
        
        # اگر کاربر وارد نشده، ابتدا حساب کاربری ایجاد می‌شود
        if not request.user.is_authenticated:
            # مشخصات کاربر
            username = data.get('username', '').strip()
            email = data.get('email', '').strip()
            password = data.get('password', '')
            first_name = data.get('first_name', '').strip()
            last_name = data.get('last_name', '').strip()
            
            # اعتبارسنجی
            if User.objects.filter(username=username).exists():
                return Response({
                    'error': 'نام کاربری قبلاً استفاده شده است'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if User.objects.filter(email=email).exists():
                return Response({
                    'error': 'ایمیل قبلاً استفاده شده است'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # ایجاد کاربر
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
        else:
            user = request.user
        
        # مشخصات فروشگاه
        from .models import Store
        
        store_name = data.get('store_name', '').strip()
        store_domain = data.get('store_domain', '').strip()
        store_description = data.get('store_description', '').strip()
        store_phone = data.get('store_phone', '').strip()
        store_address = data.get('store_address', '').strip()
        
        if not store_name:
            return Response({
                'error': 'نام فروشگاه الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not store_domain:
            return Response({
                'error': 'دامنه فروشگاه الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # چک کردن یکتا بودن دامنه
        if Store.objects.filter(domain=store_domain).exists():
            return Response({
                'error': 'دامنه قبلاً استفاده شده است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # ایجاد فروشگاه
        with transaction.atomic():
            store = Store.objects.create(
                owner=user,
                name=store_name,
                domain=store_domain,
                description=store_description,
                phone=store_phone,
                address=store_address,
                email=user.email,
                is_active=False,  # نیاز به تایید مدیر پلتفرم
                is_approved=False
            )
            
            # ایجاد توکن برای کاربر
            token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'message': 'درخواست فروشگاه با موفقیت ثبت شد و در انتظار تایید مدیر است',
            'store': {
                'id': str(store.id),
                'name': store.name,
                'domain': store.domain,
                'is_approved': store.is_approved,
            },
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
            },
            'token': token.key
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'error': f'خطا در ثبت درخواست: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
