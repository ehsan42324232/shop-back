from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.core.files.base import ContentFile
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
import pandas as pd
from io import BytesIO

from .models import Store, BulkImportLog
from .utils import process_bulk_import, generate_sample_import_template


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_import_products(request):
    """
    ایمپورت گروهی محصولات از فایل CSV/Excel
    """
    try:
        # بررسی دسترسی به فروشگاه
        if not hasattr(request, 'store') or not request.store:
            return Response({
                'error': 'فروشگاه یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # بررسی مالکیت فروشگاه
        if not hasattr(request, 'is_store_owner') or not request.is_store_owner:
            return Response({
                'error': 'فقط مالک فروشگاه می‌تواند محصولات را ایمپورت کند'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # بررسی وجود فایل
        if 'file' not in request.FILES:
            return Response({
                'error': 'فایل ارسال نشده است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = request.FILES['file']
        
        # بررسی نوع فایل
        allowed_extensions = ['.csv', '.xlsx', '.xls']
        file_extension = uploaded_file.name.lower().split('.')[-1]
        
        if f'.{file_extension}' not in allowed_extensions:
            return Response({
                'error': 'فرمت فایل پشتیبانی نمی‌شود. فرمت‌های مجاز: CSV, Excel'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # بررسی حجم فایل (حداکثر 10 مگابایت)
        max_file_size = 10 * 1024 * 1024  # 10 MB
        if uploaded_file.size > max_file_size:
            return Response({
                'error': 'حجم فایل نباید بیشتر از 10 مگابایت باشد'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # پردازش فایل
        result = process_bulk_import(uploaded_file, request.store, request.user)
        
        if result['status'] == 'completed':
            return Response({
                'message': result['message'],
                'status': result['status'],
                'details': result['details']
            }, status=status.HTTP_200_OK)
        
        elif result['status'] == 'partial':
            return Response({
                'message': result['message'],
                'status': result['status'],
                'details': result['details'],
                'warnings': 'برخی محصولات با خطا مواجه شدند'
            }, status=status.HTTP_206_PARTIAL_CONTENT)
        
        else:  # failed
            return Response({
                'error': result['message'],
                'status': result['status'],
                'details': result['details']
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        return Response({
            'error': f'خطا در پردازش فایل: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_import_logs(request):
    """
    دریافت تاریخچه ایمپورت محصولات
    """
    try:
        if not hasattr(request, 'store') or not request.store:
            return Response({
                'error': 'فروشگاه یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # بررسی مالکیت فروشگاه
        if not hasattr(request, 'is_store_owner') or not request.is_store_owner:
            return Response({
                'error': 'فقط مالک فروشگاه می‌تواند تاریخچه را مشاهده کند'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # دریافت لاگ‌ها
        logs = BulkImportLog.objects.filter(store=request.store).order_by('-created_at')[:20]
        
        logs_data = []
        for log in logs:
            logs_data.append({
                'id': log.id,
                'filename': log.filename,
                'status': log.status,
                'total_rows': log.total_rows,
                'successful_rows': log.successful_rows,
                'failed_rows': log.failed_rows,
                'categories_created': log.categories_created,
                'products_created': log.products_created,
                'products_updated': log.products_updated,
                'created_at': log.created_at,
                'error_details': log.error_details[:5] if log.error_details else []  # نمایش 5 خطای اول
            })
        
        return Response({
            'import_logs': logs_data
        })
        
    except Exception as e:
        return Response({
            'error': f'خطا در دریافت تاریخچه: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_import_log_detail(request, log_id):
    """
    دریافت جزئیات کامل لاگ ایمپورت
    """
    try:
        if not hasattr(request, 'store') or not request.store:
            return Response({
                'error': 'فروشگاه یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # بررسی مالکیت فروشگاه
        if not hasattr(request, 'is_store_owner') or not request.is_store_owner:
            return Response({
                'error': 'فقط مالک فروشگاه می‌تواند جزئیات را مشاهده کند'
            }, status=status.HTTP_403_FORBIDDEN)
        
        log = get_object_or_404(BulkImportLog, id=log_id, store=request.store)
        
        return Response({
            'log': {
                'id': log.id,
                'filename': log.filename,
                'status': log.status,
                'total_rows': log.total_rows,
                'successful_rows': log.successful_rows,
                'failed_rows': log.failed_rows,
                'categories_created': log.categories_created,
                'products_created': log.products_created,
                'products_updated': log.products_updated,
                'created_at': log.created_at,
                'error_details': log.error_details,
                'user': {
                    'username': log.user.username,
                    'name': f'{log.user.first_name} {log.user.last_name}'
                }
            }
        })
        
    except Exception as e:
        return Response({
            'error': f'خطا در دریافت جزئیات: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def download_sample_template(request):
    """
    دانلود فایل نمونه برای ایمپورت محصولات
    """
    try:
        # تولید فایل نمونه
        df = generate_sample_import_template()
        
        # ایجاد فایل Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='محصولات', index=False)
        
        output.seek(0)
        
        # ایجاد پاسخ HTTP
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="product_import_template.xlsx"'
        
        return response
        
    except Exception as e:
        return Response({
            'error': f'خطا در تولید فایل نمونه: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_import_file(request):
    """
    اعتبارسنجی فایل ایمپورت قبل از پردازش
    """
    try:
        if not hasattr(request, 'store') or not request.store:
            return Response({
                'error': 'فروشگاه یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # بررسی مالکیت فروشگاه
        if not hasattr(request, 'is_store_owner') or not request.is_store_owner:
            return Response({
                'error': 'فقط مالک فروشگاه می‌تواند فایل را اعتبارسنجی کند'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if 'file' not in request.FILES:
            return Response({
                'error': 'فایل ارسال نشده است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = request.FILES['file']
        
        try:
            # خواندن فایل
            file_extension = uploaded_file.name.lower().split('.')[-1]
            
            if file_extension == 'csv':
                df = pd.read_csv(uploaded_file)
            elif file_extension in ['xlsx', 'xls']:
                df = pd.read_excel(uploaded_file)
            else:
                return Response({
                    'error': 'فرمت فایل پشتیبانی نمی‌شود'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # اعتبارسنجی ستون‌ها
            required_columns = ['title', 'price']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            validation_result = {
                'is_valid': True,
                'total_rows': len(df),
                'columns': list(df.columns),
                'missing_required_columns': missing_columns,
                'warnings': [],
                'errors': []
            }
            
            if missing_columns:
                validation_result['is_valid'] = False
                validation_result['errors'].append(f'ستون‌های اجباری موجود نیستند: {", ".join(missing_columns)}')
            
            # بررسی وجود ستون‌های دسته‌بندی
            category_columns = [col for col in df.columns if col.startswith('category_level_')]
            if not category_columns:
                validation_result['warnings'].append('ستون دسته‌بندی یافت نشد')
            
            # بررسی ستون‌های ویژگی
            attribute_columns = [col for col in df.columns if col.startswith('attribute_')]
            attribute_pairs = len([col for col in attribute_columns if col.endswith('_name')])
            
            if attribute_pairs > 0:
                validation_result['attribute_pairs_found'] = attribute_pairs
            
            # بررسی نمونه داده‌ها
            sample_rows = []
            for index, row in df.head(3).iterrows():
                sample_row = {}
                for col in df.columns:
                    sample_row[col] = str(row[col]) if pd.notna(row[col]) else ''
                sample_rows.append(sample_row)
            
            validation_result['sample_data'] = sample_rows
            
            # بررسی خطاهای احتمالی در داده‌ها
            empty_titles = df[df['title'].isna() | (df['title'] == '')].shape[0]
            if empty_titles > 0:
                validation_result['warnings'].append(f'{empty_titles} ردیف بدون عنوان محصول')
            
            invalid_prices = df[df['price'].isna() | (df['price'] <= 0)].shape[0]
            if invalid_prices > 0:
                validation_result['warnings'].append(f'{invalid_prices} ردیف با قیمت نامعتبر')
            
            return Response(validation_result)
            
        except Exception as e:
            return Response({
                'is_valid': False,
                'error': f'خطا در خواندن فایل: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        return Response({
            'error': f'خطا در اعتبارسنجی: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def export_products(request):
    """
    اکسپورت محصولات فروشگاه به فرمت Excel
    """
    try:
        if not hasattr(request, 'store') or not request.store:
            return Response({
                'error': 'فروشگاه یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # بررسی مالکیت فروشگاه
        if not hasattr(request, 'is_store_owner') or not request.is_store_owner:
            return Response({
                'error': 'فقط مالک فروشگاه می‌تواند محصولات را اکسپورت کند'
            }, status=status.HTTP_403_FORBIDDEN)
        
        from .utils import export_products_to_csv
        
        # دریافت فیلترها از درخواست
        data = json.loads(request.body) if request.body else {}
        
        # فیلتر محصولات
        products = request.store.products.all()
        
        if data.get('category_id'):
            products = products.filter(category_id=data['category_id'])
        
        if data.get('is_active') is not None:
            products = products.filter(is_active=data['is_active'])
        
        if data.get('is_featured') is not None:
            products = products.filter(is_featured=data['is_featured'])
        
        # اکسپورت به DataFrame
        df = export_products_to_csv(request.store, products)
        
        # ایجاد فایل Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='محصولات', index=False)
        
        output.seek(0)
        
        # نام فایل
        filename = f"{request.store.name}_products_export.xlsx"
        
        # ایجاد پاسخ HTTP
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        return Response({
            'error': f'خطا در اکسپورت محصولات: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_import_statistics(request):
    """
    دریافت آمار ایمپورت محصولات
    """
    try:
        if not hasattr(request, 'store') or not request.store:
            return Response({
                'error': 'فروشگاه یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # بررسی مالکیت فروشگاه
        if not hasattr(request, 'is_store_owner') or not request.is_store_owner:
            return Response({
                'error': 'فقط مالک فروشگاه می‌تواند آمار را مشاهده کند'
            }, status=status.HTTP_403_FORBIDDEN)
        
        from django.db.models import Sum, Count
        
        # آمار کلی ایمپورت
        logs = BulkImportLog.objects.filter(store=request.store)
        
        stats = {
            'total_imports': logs.count(),
            'successful_imports': logs.filter(status='completed').count(),
            'failed_imports': logs.filter(status='failed').count(),
            'partial_imports': logs.filter(status='partial').count(),
            'total_products_created': logs.aggregate(total=Sum('products_created'))['total'] or 0,
            'total_products_updated': logs.aggregate(total=Sum('products_updated'))['total'] or 0,
            'total_categories_created': logs.aggregate(total=Sum('categories_created'))['total'] or 0,
            'last_import': logs.first().created_at if logs.exists() else None
        }
        
        # آمار ماهانه (آخرین 6 ماه)
        from datetime import datetime, timedelta
        from django.db.models import Count
        from django.db.models.functions import TruncMonth
        
        six_months_ago = datetime.now() - timedelta(days=180)
        monthly_stats = logs.filter(created_at__gte=six_months_ago).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            count=Count('id'),
            products_created=Sum('products_created'),
            categories_created=Sum('categories_created')
        ).order_by('month')
        
        stats['monthly_stats'] = list(monthly_stats)
        
        return Response({
            'statistics': stats
        })
        
    except Exception as e:
        return Response({
            'error': f'خطا در دریافت آمار: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_import_log(request, log_id):
    """
    حذف لاگ ایمپورت
    """
    try:
        if not hasattr(request, 'store') or not request.store:
            return Response({
                'error': 'فروشگاه یافت نشد'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # بررسی مالکیت فروشگاه
        if not hasattr(request, 'is_store_owner') or not request.is_store_owner:
            return Response({
                'error': 'فقط مالک فروشگاه می‌تواند لاگ را حذف کند'
            }, status=status.HTTP_403_FORBIDDEN)
        
        log = get_object_or_404(BulkImportLog, id=log_id, store=request.store)
        log.delete()
        
        return Response({
            'message': 'لاگ ایمپورت با موفقیت حذف شد'
        })
        
    except Exception as e:
        return Response({
            'error': f'خطا در حذف لاگ: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
