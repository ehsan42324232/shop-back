# shop/sms_campaign_views.py
"""
Mall Platform - SMS Campaign API Views
RESTful API for SMS campaign management
"""
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Sum, Count
import logging
from datetime import timedelta

from .models import Store
from .sms_campaign_system import (
    SMSTemplate, CustomerSegment, SMSCampaign, 
    SMSDeliveryReport, SMSCampaignAnalytics
)

logger = logging.getLogger(__name__)

# SMS Template Views
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def sms_templates(request):
    """Get all templates or create new template"""
    try:
        store = get_object_or_404(Store, owner=request.user)
        
        if request.method == 'GET':
            templates = SMSTemplate.objects.filter(store=store).order_by('-created_at')
            
            template_data = []
            for template in templates:
                template_data.append({
                    'id': template.id,
                    'name': template.name,
                    'template_type': template.template_type,
                    'subject': template.subject,
                    'message': template.message,
                    'variables': template.variables,
                    'is_active': template.is_active,
                    'send_immediately': template.send_immediately,
                    'created_at': template.created_at,
                    'updated_at': template.updated_at
                })
            
            return Response({
                'success': True,
                'templates': template_data
            })
            
        elif request.method == 'POST':
            data = request.data
            
            # Validate required fields
            required_fields = ['name', 'template_type', 'subject', 'message']
            for field in required_fields:
                if not data.get(field):
                    return Response({
                        'success': False,
                        'message': f'فیلد {field} الزامی است'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check message length
            if len(data['message']) > 500:
                return Response({
                    'success': False,
                    'message': 'متن پیام نمی‌تواند بیش از ۵۰۰ کاراکتر باشد'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            template = SMSTemplate.objects.create(
                store=store,
                name=data['name'],
                template_type=data['template_type'],
                subject=data['subject'],
                message=data['message'],
                variables=data.get('variables', []),
                is_active=data.get('is_active', True),
                send_immediately=data.get('send_immediately', False)
            )
            
            return Response({
                'success': True,
                'template_id': template.id,
                'message': 'قالب پیامک با موفقیت ایجاد شد'
            })
            
    except Exception as e:
        logger.error(f"SMS templates error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در پردازش درخواست'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def sms_template_detail(request, template_id):
    """Get, update, or delete specific template"""
    try:
        store = get_object_or_404(Store, owner=request.user)
        template = get_object_or_404(SMSTemplate, id=template_id, store=store)
        
        if request.method == 'GET':
            return Response({
                'success': True,
                'template': {
                    'id': template.id,
                    'name': template.name,
                    'template_type': template.template_type,
                    'subject': template.subject,
                    'message': template.message,
                    'variables': template.variables,
                    'is_active': template.is_active,
                    'send_immediately': template.send_immediately,
                    'created_at': template.created_at,
                    'updated_at': template.updated_at
                }
            })
            
        elif request.method == 'PUT':
            data = request.data
            
            # Update fields
            if 'name' in data:
                template.name = data['name']
            if 'template_type' in data:
                template.template_type = data['template_type']
            if 'subject' in data:
                template.subject = data['subject']
            if 'message' in data:
                if len(data['message']) > 500:
                    return Response({
                        'success': False,
                        'message': 'متن پیام نمی‌تواند بیش از ۵۰۰ کاراکتر باشد'
                    }, status=status.HTTP_400_BAD_REQUEST)
                template.message = data['message']
            if 'variables' in data:
                template.variables = data['variables']
            if 'is_active' in data:
                template.is_active = data['is_active']
            if 'send_immediately' in data:
                template.send_immediately = data['send_immediately']
                
            template.save()
            
            return Response({
                'success': True,
                'message': 'قالب پیامک با موفقیت بروزرسانی شد'
            })
            
        elif request.method == 'DELETE':
            template.delete()
            return Response({
                'success': True,
                'message': 'قالب پیامک با موفقیت حذف شد'
            })
            
    except Exception as e:
        logger.error(f"SMS template detail error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در پردازش درخواست'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Customer Segment Views
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def customer_segments(request):
    """Get all segments or create new segment"""
    try:
        store = get_object_or_404(Store, owner=request.user)
        
        if request.method == 'GET':
            segments = CustomerSegment.objects.filter(store=store).order_by('-created_at')
            
            segment_data = []
            for segment in segments:
                segment_data.append({
                    'id': segment.id,
                    'name': segment.name,
                    'segment_type': segment.segment_type,
                    'description': segment.description,
                    'criteria': segment.criteria,
                    'customer_count': segment.customer_count,
                    'last_updated': segment.last_updated,
                    'created_at': segment.created_at
                })
            
            return Response({
                'success': True,
                'segments': segment_data
            })
            
        elif request.method == 'POST':
            data = request.data
            
            required_fields = ['name', 'segment_type']
            for field in required_fields:
                if not data.get(field):
                    return Response({
                        'success': False,
                        'message': f'فیلد {field} الزامی است'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            segment = CustomerSegment.objects.create(
                store=store,
                name=data['name'],
                segment_type=data['segment_type'],
                description=data.get('description', ''),
                criteria=data.get('criteria', {})
            )
            
            # Update customer count
            segment.update_customer_count()
            
            return Response({
                'success': True,
                'segment_id': segment.id,
                'customer_count': segment.customer_count,
                'message': 'بخش مشتریان با موفقیت ایجاد شد'
            })
            
    except Exception as e:
        logger.error(f"Customer segments error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در پردازش درخواست'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Campaign Views (continued)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def template_variables(request):
    """Get available template variables"""
    variables = {
        'customer': [
            {'name': 'name', 'description': 'نام مشتری', 'example': 'احمد محمدی'},
            {'name': 'first_name', 'description': 'نام', 'example': 'احمد'},
            {'name': 'last_name', 'description': 'نام خانوادگی', 'example': 'محمدی'},
            {'name': 'mobile', 'description': 'شماره موبایل', 'example': '09123456789'},
            {'name': 'email', 'description': 'ایمیل', 'example': 'ahmad@example.com'}
        ],
        'store': [
            {'name': 'store_name', 'description': 'نام فروشگاه', 'example': 'فروشگاه مال'},
            {'name': 'store_phone', 'description': 'تلفن فروشگاه', 'example': '02112345678'},
            {'name': 'store_address', 'description': 'آدرس فروشگاه', 'example': 'تهران، خیابان ولیعصر'}
        ],
        'order': [
            {'name': 'order_number', 'description': 'شماره سفارش', 'example': 'ORD-1001'},
            {'name': 'order_total', 'description': 'مبلغ سفارش', 'example': '۱۵۰,۰۰۰ تومان'},
            {'name': 'order_date', 'description': 'تاریخ سفارش', 'example': '۱۴۰۳/۰۵/۱۵'},
            {'name': 'delivery_date', 'description': 'تاریخ تحویل', 'example': '۱۴۰۳/۰۵/۱۸'}
        ],
        'general': [
            {'name': 'current_date', 'description': 'تاریخ جاری', 'example': '۱۴۰۳/۰۵/۲۰'},
            {'name': 'current_time', 'description': 'زمان جاری', 'example': '۱۴:۳۰'},
            {'name': 'discount_code', 'description': 'کد تخفیف', 'example': 'SAVE20'},
            {'name': 'discount_amount', 'description': 'مبلغ تخفیف', 'example': '۲۰,۰۰۰ تومان'}
        ]
    }
    
    return Response({
        'success': True,
        'variables': variables
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def preview_template(request):
    """Preview template with sample data"""
    try:
        template_message = request.data.get('message', '')
        template_type = request.data.get('template_type', 'custom')
        
        # Sample context data
        sample_context = {
            'name': 'احمد محمدی',
            'first_name': 'احمد',
            'last_name': 'محمدی',
            'mobile': '09123456789',
            'email': 'ahmad@example.com',
            'store_name': 'فروشگاه مال',
            'store_phone': '02112345678',
            'store_address': 'تهران، خیابان ولیعصر',
            'order_number': 'ORD-1001',
            'order_total': '۱۵۰,۰۰۰ تومان',
            'order_date': '۱۴۰۳/۰۵/۱۵',
            'delivery_date': '۱۴۰۳/۰۵/۱۸',
            'current_date': '۱۴۰۳/۰۵/۲۰',
            'current_time': '۱۴:۳۰',
            'discount_code': 'SAVE20',
            'discount_amount': '۲۰,۰۰۰ تومان'
        }
        
        # Render message with sample data
        preview_message = template_message
        for key, value in sample_context.items():
            placeholder = f"{{{{{key}}}}}"
            preview_message = preview_message.replace(placeholder, str(value))
        
        # Calculate character count
        char_count = len(preview_message)
        sms_count = (char_count + 69) // 70  # 70 chars per SMS
        
        return Response({
            'success': True,
            'preview': {
                'message': preview_message,
                'character_count': char_count,
                'sms_count': sms_count,
                'estimated_cost': sms_count * 500  # 500 Rials per SMS
            }
        })
        
    except Exception as e:
        logger.error(f"Template preview error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در پیش‌نمایش قالب'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sms_dashboard(request):
    """Get SMS campaign dashboard data"""
    try:
        store = get_object_or_404(Store, owner=request.user)
        
        # Recent campaigns (last 10)
        recent_campaigns = SMSCampaign.objects.filter(
            store=store
        ).order_by('-created_at')[:10]
        
        # Campaign statistics
        total_campaigns = SMSCampaign.objects.filter(store=store).count()
        active_campaigns = SMSCampaign.objects.filter(
            store=store,
            status__in=['sending', 'scheduled']
        ).count()
        
        # SMS statistics (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        campaigns_last_30 = SMSCampaign.objects.filter(
            store=store,
            created_at__gte=thirty_days_ago
        )
        
        total_sent = campaigns_last_30.aggregate(
            total=Sum('sent_count')
        )['total'] or 0
        
        total_delivered = campaigns_last_30.aggregate(
            total=Sum('delivered_count')
        )['total'] or 0
        
        total_cost = campaigns_last_30.aggregate(
            total=Sum('actual_cost')
        )['total'] or 0
        
        delivery_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0
        
        # Template statistics
        template_count = SMSTemplate.objects.filter(store=store).count()
        active_templates = SMSTemplate.objects.filter(
            store=store,
            is_active=True
        ).count()
        
        # Segment statistics
        segment_count = CustomerSegment.objects.filter(store=store).count()
        total_customers = CustomerSegment.objects.filter(
            store=store
        ).aggregate(total=Sum('customer_count'))['total'] or 0
        
        # Recent delivery reports
        recent_deliveries = SMSDeliveryReport.objects.filter(
            campaign__store=store
        ).order_by('-created_at')[:20]
        
        delivery_data = []
        for delivery in recent_deliveries:
            delivery_data.append({
                'campaign_name': delivery.campaign.name,
                'mobile_number': delivery.mobile_number[-4:].rjust(11, '*'),  # Mask number
                'status': delivery.status,
                'sent_at': delivery.sent_at,
                'delivered_at': delivery.delivered_at
            })
        
        # Campaign data
        campaign_data = []
        for campaign in recent_campaigns:
            delivery_rate_campaign = 0
            if campaign.sent_count > 0:
                delivery_rate_campaign = (campaign.delivered_count / campaign.sent_count) * 100
                
            campaign_data.append({
                'id': campaign.id,
                'name': campaign.name,
                'status': campaign.status,
                'total_recipients': campaign.total_recipients,
                'sent_count': campaign.sent_count,
                'delivered_count': campaign.delivered_count,
                'delivery_rate': round(delivery_rate_campaign, 2),
                'cost': float(campaign.actual_cost),
                'created_at': campaign.created_at
            })
        
        return Response({
            'success': True,
            'dashboard': {
                'statistics': {
                    'total_campaigns': total_campaigns,
                    'active_campaigns': active_campaigns,
                    'total_sent_30_days': total_sent,
                    'total_delivered_30_days': total_delivered,
                    'delivery_rate_30_days': round(delivery_rate, 2),
                    'total_cost_30_days': float(total_cost),
                    'template_count': template_count,
                    'active_templates': active_templates,
                    'segment_count': segment_count,
                    'total_customers': total_customers
                },
                'recent_campaigns': campaign_data,
                'recent_deliveries': delivery_data
            }
        })
        
    except Exception as e:
        logger.error(f"SMS dashboard error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در دریافت داشبورد پیامک'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_sms(request):
    """Send test SMS"""
    try:
        store = get_object_or_404(Store, owner=request.user)
        
        mobile = request.data.get('mobile')
        message = request.data.get('message')
        
        if not mobile or not message:
            return Response({
                'success': False,
                'message': 'شماره موبایل و متن پیام الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate Iranian mobile number
        import re
        if not re.match(r'^09\d{9}$', mobile):
            return Response({
                'success': False,
                'message': 'شماره موبایل معتبر نیست'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Send test SMS
        from .enhanced_sms_service import sms_service
        
        result = sms_service.send_sms(
            phone_number=mobile,
            message=message,
            template_type='test'
        )
        
        if result.get('success'):
            return Response({
                'success': True,
                'message': 'پیامک آزمایشی با موفقیت ارسال شد',
                'message_id': result.get('message_id')
            })
        else:
            return Response({
                'success': False,
                'message': result.get('message', 'خطا در ارسال پیامک آزمایشی')
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Test SMS error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در ارسال پیامک آزمایشی'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def segment_preview(request, segment_id):
    """Preview customers in a segment"""
    try:
        store = get_object_or_404(Store, owner=request.user)
        segment = get_object_or_404(CustomerSegment, id=segment_id, store=store)
        
        customers = segment.get_customers()
        
        # Pagination
        page = int(request.GET.get('page', 1))
        per_page = min(int(request.GET.get('per_page', 50)), 100)  # Max 100
        start = (page - 1) * per_page
        end = start + per_page
        
        total = len(customers)
        customers_page = customers[start:end]
        
        customer_data = []
        for customer in customers_page:
            customer_data.append({
                'id': customer.id,
                'name': customer.get_full_name(),
                'mobile': customer.mobile if hasattr(customer, 'mobile') else '',
                'email': customer.email if hasattr(customer, 'email') else '',
                'date_joined': customer.date_joined if hasattr(customer, 'date_joined') else None
            })
        
        return Response({
            'success': True,
            'customers': customer_data,
            'pagination': {
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        logger.error(f"Segment preview error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در پیش‌نمایش بخش مشتریان'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_import_recipients(request):
    """Bulk import recipients from CSV/Excel"""
    try:
        store = get_object_or_404(Store, owner=request.user)
        
        if 'file' not in request.FILES:
            return Response({
                'success': False,
                'message': 'فایل الزامی است'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file']
        
        # Validate file type
        if not file.name.endswith(('.csv', '.xlsx', '.xls')):
            return Response({
                'success': False,
                'message': 'تنها فایل‌های CSV و Excel پشتیبانی می‌شوند'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        recipients = []
        errors = []
        
        try:
            if file.name.endswith('.csv'):
                # Process CSV file
                import csv
                import io
                
                file_content = file.read().decode('utf-8')
                csv_reader = csv.DictReader(io.StringIO(file_content))
                
                for row_num, row in enumerate(csv_reader, start=2):
                    mobile = row.get('mobile', '').strip()
                    name = row.get('name', '').strip()
                    
                    if not mobile:
                        errors.append(f'ردیف {row_num}: شماره موبایل الزامی است')
                        continue
                    
                    # Validate mobile number
                    import re
                    if not re.match(r'^09\d{9}$', mobile):
                        errors.append(f'ردیف {row_num}: شماره موبایل {mobile} معتبر نیست')
                        continue
                    
                    recipients.append({
                        'mobile': mobile,
                        'name': name or 'نامشخص'
                    })
            
            else:
                # Process Excel file
                import pandas as pd
                
                df = pd.read_excel(file)
                
                for index, row in df.iterrows():
                    row_num = index + 2
                    mobile = str(row.get('mobile', '')).strip()
                    name = str(row.get('name', '')).strip()
                    
                    if not mobile or mobile == 'nan':
                        errors.append(f'ردیف {row_num}: شماره موبایل الزامی است')
                        continue
                    
                    # Validate mobile number
                    import re
                    if not re.match(r'^09\d{9}$', mobile):
                        errors.append(f'ردیف {row_num}: شماره موبایل {mobile} معتبر نیست')
                        continue
                    
                    recipients.append({
                        'mobile': mobile,
                        'name': name if name != 'nan' else 'نامشخص'
                    })
        
        except Exception as e:
            return Response({
                'success': False,
                'message': f'خطا در خواندن فایل: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Remove duplicates
        unique_recipients = []
        seen_mobiles = set()
        
        for recipient in recipients:
            if recipient['mobile'] not in seen_mobiles:
                unique_recipients.append(recipient)
                seen_mobiles.add(recipient['mobile'])
        
        return Response({
            'success': True,
            'recipients': unique_recipients,
            'total_imported': len(unique_recipients),
            'total_errors': len(errors),
            'errors': errors[:10]  # Show first 10 errors
        })
        
    except Exception as e:
        logger.error(f"Bulk import error: {e}")
        return Response({
            'success': False,
            'message': 'خطا در پردازش فایل'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
