# shop/sms_campaign_system.py
"""
Mall Platform - Complete SMS Campaign Management System
Advanced SMS marketing and customer segmentation for Iranian market
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import RegexValidator
from decimal import Decimal
import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from celery import shared_task
import json

from .models import Store, Customer
from .order_models import Order
from .enhanced_sms_service import sms_service

logger = logging.getLogger(__name__)

# SMS Campaign Models
class SMSTemplate(models.Model):
    """SMS message templates"""
    TEMPLATE_TYPES = [
        ('welcome', 'خوش‌آمدگویی'),
        ('order_confirmation', 'تایید سفارش'),
        ('shipping_notification', 'اطلاع‌رسانی ارسال'),
        ('delivery_confirmation', 'تایید تحویل'),
        ('payment_reminder', 'یادآوری پرداخت'),
        ('promotion', 'تبلیغات و تخفیف'),
        ('birthday', 'تبریک تولد'),
        ('abandoned_cart', 'سبد خرید رها شده'),
        ('feedback_request', 'درخواست نظر'),
        ('loyalty_reward', 'پاداش وفاداری'),
        ('custom', 'سفارشی')
    ]
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='sms_templates')
    name = models.CharField(max_length=100, verbose_name='نام قالب')
    template_type = models.CharField(max_length=30, choices=TEMPLATE_TYPES, verbose_name='نوع قالب')
    subject = models.CharField(max_length=50, verbose_name='موضوع')
    message = models.TextField(max_length=500, verbose_name='متن پیام')
    
    # Dynamic variables support
    variables = models.JSONField(default=list, verbose_name='متغیرهای پویا')
    
    # Settings
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    send_immediately = models.BooleanField(default=False, verbose_name='ارسال فوری')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'قالب پیامک'
        verbose_name_plural = 'قالب‌های پیامک'
        
    def __str__(self):
        return f"{self.store.name} - {self.name}"
        
    def render_message(self, context: Dict[str, Any]) -> str:
        """Render message with context variables"""
        message = self.message
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            message = message.replace(placeholder, str(value))
        return message


class CustomerSegment(models.Model):
    """Customer segmentation for targeted SMS campaigns"""
    SEGMENT_TYPES = [
        ('all_customers', 'همه مشتریان'),
        ('new_customers', 'مشتریان جدید'),
        ('returning_customers', 'مشتریان بازگشتی'),
        ('high_value', 'مشتریان پرارزش'),
        ('inactive', 'مشتریان غیرفعال'),
        ('birthday_this_month', 'تولد این ماه'),
        ('location_based', 'بر اساس موقعیت'),
        ('purchase_behavior', 'بر اساس رفتار خرید'),
        ('custom', 'سفارشی')
    ]
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='customer_segments')
    name = models.CharField(max_length=100, verbose_name='نام بخش')
    segment_type = models.CharField(max_length=30, choices=SEGMENT_TYPES, verbose_name='نوع بخش‌بندی')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    
    # Segmentation criteria
    criteria = models.JSONField(default=dict, verbose_name='معیارهای بخش‌بندی')
    
    # Cache
    customer_count = models.PositiveIntegerField(default=0, verbose_name='تعداد مشتریان')
    last_updated = models.DateTimeField(auto_now=True, verbose_name='آخرین بروزرسانی')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'بخش مشتریان'
        verbose_name_plural = 'بخش‌های مشتریان'
        
    def __str__(self):
        return f"{self.store.name} - {self.name}"
        
    def get_customers(self) -> List[Customer]:
        """Get customers matching this segment criteria"""
        if self.segment_type == 'all_customers':
            return list(Customer.objects.filter(store=self.store))
            
        elif self.segment_type == 'new_customers':
            days_threshold = self.criteria.get('days', 30)
            since_date = timezone.now() - timedelta(days=days_threshold)
            return list(Customer.objects.filter(
                store=self.store,
                date_joined__gte=since_date
            ))
            
        elif self.segment_type == 'returning_customers':
            min_orders = self.criteria.get('min_orders', 2)
            customers_with_orders = Order.objects.filter(
                store=self.store
            ).values('customer').annotate(
                order_count=models.Count('id')
            ).filter(order_count__gte=min_orders)
            
            customer_ids = [item['customer'] for item in customers_with_orders]
            return list(Customer.objects.filter(id__in=customer_ids))
            
        elif self.segment_type == 'high_value':
            min_amount = Decimal(str(self.criteria.get('min_amount', 1000000)))
            high_value_customers = Order.objects.filter(
                store=self.store,
                status='delivered'
            ).values('customer').annotate(
                total_spent=models.Sum('total_amount')
            ).filter(total_spent__gte=min_amount)
            
            customer_ids = [item['customer'] for item in high_value_customers]
            return list(Customer.objects.filter(id__in=customer_ids))
            
        elif self.segment_type == 'inactive':
            days_threshold = self.criteria.get('days', 90)
            since_date = timezone.now() - timedelta(days=days_threshold)
            
            active_customer_ids = Order.objects.filter(
                store=self.store,
                created_at__gte=since_date
            ).values_list('customer_id', flat=True).distinct()
            
            return list(Customer.objects.filter(
                store=self.store
            ).exclude(id__in=active_customer_ids))
            
        elif self.segment_type == 'birthday_this_month':
            current_month = timezone.now().month
            return list(Customer.objects.filter(
                store=self.store,
                birth_date__month=current_month
            ))
            
        elif self.segment_type == 'location_based':
            city = self.criteria.get('city')
            province = self.criteria.get('province')
            filters = {'store': self.store}
            if city:
                filters['city__icontains'] = city
            if province:
                filters['province__icontains'] = province
            return list(Customer.objects.filter(**filters))
            
        elif self.segment_type == 'custom':
            # Custom SQL query or complex filtering
            return self._execute_custom_criteria()
            
        return []
        
    def _execute_custom_criteria(self) -> List[Customer]:
        """Execute custom segmentation criteria"""
        try:
            # This would be expanded based on specific custom criteria
            # For now, return empty list
            return []
        except Exception as e:
            logger.error(f"Error executing custom criteria: {e}")
            return []
            
    def update_customer_count(self):
        """Update cached customer count"""
        self.customer_count = len(self.get_customers())
        self.save(update_fields=['customer_count', 'last_updated'])


class SMSCampaign(models.Model):
    """SMS Campaign management"""
    CAMPAIGN_STATUS = [
        ('draft', 'پیش‌نویس'),
        ('scheduled', 'زمان‌بندی شده'),
        ('sending', 'در حال ارسال'),
        ('completed', 'تکمیل شده'),
        ('paused', 'متوقف شده'),
        ('cancelled', 'لغو شده'),
        ('failed', 'ناموفق')
    ]
    
    SEND_TYPES = [
        ('immediate', 'فوری'),
        ('scheduled', 'زمان‌بندی شده'),
        ('recurring', 'تکراری')
    ]
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='sms_campaigns')
    name = models.CharField(max_length=100, verbose_name='نام کمپین')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    
    # Message
    template = models.ForeignKey(SMSTemplate, on_delete=models.CASCADE, verbose_name='قالب پیام')
    custom_message = models.TextField(max_length=500, blank=True, verbose_name='پیام سفارشی')
    
    # Target audience
    segments = models.ManyToManyField(CustomerSegment, verbose_name='بخش‌های هدف')
    custom_recipients = models.JSONField(default=list, verbose_name='گیرندگان سفارشی')
    
    # Scheduling
    send_type = models.CharField(max_length=20, choices=SEND_TYPES, default='immediate', verbose_name='نوع ارسال')
    scheduled_at = models.DateTimeField(blank=True, null=True, verbose_name='زمان ارسال')
    
    # Recurring settings
    is_recurring = models.BooleanField(default=False, verbose_name='تکراری')
    recurrence_pattern = models.JSONField(default=dict, verbose_name='الگوی تکرار')
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=CAMPAIGN_STATUS, default='draft', verbose_name='وضعیت')
    
    # Statistics
    total_recipients = models.PositiveIntegerField(default=0, verbose_name='تعداد کل گیرندگان')
    sent_count = models.PositiveIntegerField(default=0, verbose_name='تعداد ارسال شده')
    delivered_count = models.PositiveIntegerField(default=0, verbose_name='تعداد تحویل شده')
    failed_count = models.PositiveIntegerField(default=0, verbose_name='تعداد ناموفق')
    
    # Cost tracking
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='هزینه تخمینی')
    actual_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='هزینه واقعی')
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='ایجادکننده')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(blank=True, null=True, verbose_name='زمان شروع')
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name='زمان تکمیل')
    
    class Meta:
        verbose_name = 'کمپین پیامکی'
        verbose_name_plural = 'کمپین‌های پیامکی'
        
    def __str__(self):
        return f"{self.store.name} - {self.name}"
        
    def get_recipients(self) -> List[Dict[str, Any]]:
        """Get all campaign recipients"""
        recipients = []
        
        # Add segment recipients
        for segment in self.segments.all():
            customers = segment.get_customers()
            for customer in customers:
                if hasattr(customer, 'mobile') and customer.mobile:
                    recipients.append({
                        'customer_id': customer.id,
                        'name': customer.get_full_name(),
                        'mobile': customer.mobile,
                        'source': f'segment_{segment.id}'
                    })
        
        # Add custom recipients
        for recipient in self.custom_recipients:
            recipients.append({
                'customer_id': recipient.get('customer_id'),
                'name': recipient.get('name', ''),
                'mobile': recipient.get('mobile'),
                'source': 'custom'
            })
        
        # Remove duplicates by mobile number
        unique_recipients = {}
        for recipient in recipients:
            mobile = recipient['mobile']
            if mobile and mobile not in unique_recipients:
                unique_recipients[mobile] = recipient
                
        return list(unique_recipients.values())
        
    def estimate_cost(self) -> Decimal:
        """Estimate campaign cost"""
        recipients = self.get_recipients()
        cost_per_sms = Decimal('0.50')  # 500 Rials per SMS
        return len(recipients) * cost_per_sms
        
    def start_campaign(self):
        """Start the SMS campaign"""
        try:
            recipients = self.get_recipients()
            self.total_recipients = len(recipients)
            
            if self.send_type == 'immediate':
                self.status = 'sending'
                self.started_at = timezone.now()
                self.save()
                
                # Queue SMS sending task
                send_campaign_sms.delay(self.id)
                
            elif self.send_type == 'scheduled':
                self.status = 'scheduled'
                self.save()
                
                # Schedule task
                send_campaign_sms.apply_async(
                    args=[self.id],
                    eta=self.scheduled_at
                )
                
            return True
            
        except Exception as e:
            logger.error(f"Error starting campaign {self.id}: {e}")
            self.status = 'failed'
            self.save()
            return False
            
    def pause_campaign(self):
        """Pause ongoing campaign"""
        if self.status == 'sending':
            self.status = 'paused'
            self.save()
            return True
        return False
        
    def resume_campaign(self):
        """Resume paused campaign"""
        if self.status == 'paused':
            self.status = 'sending'
            self.save()
            send_campaign_sms.delay(self.id, resume=True)
            return True
        return False


class SMSDeliveryReport(models.Model):
    """Individual SMS delivery tracking"""
    DELIVERY_STATUS = [
        ('pending', 'در انتظار'),
        ('sent', 'ارسال شده'),
        ('delivered', 'تحویل شده'),
        ('failed', 'ناموفق'),
        ('rejected', 'رد شده')
    ]
    
    campaign = models.ForeignKey(SMSCampaign, on_delete=models.CASCADE, related_name='delivery_reports')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, blank=True, null=True)
    mobile_number = models.CharField(max_length=15, verbose_name='شماره موبایل')
    name = models.CharField(max_length=100, blank=True, verbose_name='نام')
    
    message = models.TextField(verbose_name='متن پیام')
    status = models.CharField(max_length=20, choices=DELIVERY_STATUS, default='pending', verbose_name='وضعیت')
    
    # Gateway response
    gateway_message_id = models.CharField(max_length=100, blank=True, verbose_name='شناسه درگاه')
    gateway_response = models.JSONField(default=dict, verbose_name='پاسخ درگاه')
    
    # Timing
    sent_at = models.DateTimeField(blank=True, null=True, verbose_name='زمان ارسال')
    delivered_at = models.DateTimeField(blank=True, null=True, verbose_name='زمان تحویل')
    
    # Cost
    cost = models.DecimalField(max_digits=6, decimal_places=2, default=0, verbose_name='هزینه')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'گزارش تحویل پیامک'
        verbose_name_plural = 'گزارش‌های تحویل پیامک'


# Celery Tasks
@shared_task
def send_campaign_sms(campaign_id: int, resume: bool = False):
    """Celery task to send campaign SMS messages"""
    try:
        campaign = SMSCampaign.objects.get(id=campaign_id)
        
        if campaign.status == 'cancelled':
            return
            
        recipients = campaign.get_recipients()
        message_template = campaign.custom_message or campaign.template.message
        
        # Get already sent messages if resuming
        sent_numbers = set()
        if resume:
            sent_numbers = set(
                SMSDeliveryReport.objects.filter(
                    campaign=campaign,
                    status__in=['sent', 'delivered']
                ).values_list('mobile_number', flat=True)
            )
        
        sent_count = 0
        failed_count = 0
        
        for recipient in recipients:
            # Skip if already sent and resuming
            if resume and recipient['mobile'] in sent_numbers:
                continue
                
            # Check if campaign is paused
            campaign.refresh_from_db()
            if campaign.status == 'paused' or campaign.status == 'cancelled':
                break
                
            try:
                # Render message with recipient context
                context = {
                    'name': recipient['name'],
                    'store_name': campaign.store.name,
                    'mobile': recipient['mobile']
                }
                
                if campaign.template:
                    message = campaign.template.render_message(context)
                else:
                    message = message_template
                    for key, value in context.items():
                        message = message.replace(f"{{{{{key}}}}}", str(value))
                
                # Create delivery report
                delivery_report = SMSDeliveryReport.objects.create(
                    campaign=campaign,
                    customer_id=recipient.get('customer_id'),
                    mobile_number=recipient['mobile'],
                    name=recipient['name'],
                    message=message,
                    status='pending'
                )
                
                # Send SMS
                result = sms_service.send_sms(
                    phone_number=recipient['mobile'],
                    message=message,
                    template_type='campaign'
                )
                
                if result.get('success'):
                    delivery_report.status = 'sent'
                    delivery_report.gateway_message_id = result.get('message_id', '')
                    delivery_report.sent_at = timezone.now()
                    delivery_report.cost = Decimal('0.50')  # 500 Rials
                    sent_count += 1
                else:
                    delivery_report.status = 'failed'
                    failed_count += 1
                    
                delivery_report.gateway_response = result
                delivery_report.save()
                
            except Exception as e:
                logger.error(f"Error sending SMS to {recipient['mobile']}: {e}")
                failed_count += 1
        
        # Update campaign statistics
        campaign.sent_count = sent_count
        campaign.failed_count = failed_count
        
        if not resume or campaign.sent_count >= campaign.total_recipients:
            campaign.status = 'completed'
            campaign.completed_at = timezone.now()
            
        campaign.actual_cost = campaign.sent_count * Decimal('0.50')
        campaign.save()
        
    except Exception as e:
        logger.error(f"Error in send_campaign_sms task: {e}")
        try:
            campaign = SMSCampaign.objects.get(id=campaign_id)
            campaign.status = 'failed'
            campaign.save()
        except:
            pass


@shared_task
def update_delivery_status():
    """Update SMS delivery status from gateway"""
    try:
        # Get pending delivery reports from last 24 hours
        pending_reports = SMSDeliveryReport.objects.filter(
            status='sent',
            sent_at__gte=timezone.now() - timedelta(hours=24)
        )
        
        for report in pending_reports:
            if report.gateway_message_id:
                # Check delivery status with gateway
                status_result = sms_service.check_delivery_status(
                    report.gateway_message_id
                )
                
                if status_result.get('delivered'):
                    report.status = 'delivered'
                    report.delivered_at = timezone.now()
                    report.save()
                    
                    # Update campaign statistics
                    campaign = report.campaign
                    campaign.delivered_count = campaign.delivery_reports.filter(
                        status='delivered'
                    ).count()
                    campaign.save()
                    
    except Exception as e:
        logger.error(f"Error updating delivery status: {e}")


@shared_task
def process_automated_campaigns():
    """Process automated/recurring campaigns"""
    try:
        now = timezone.now()
        
        # Get scheduled campaigns that should start
        scheduled_campaigns = SMSCampaign.objects.filter(
            status='scheduled',
            scheduled_at__lte=now
        )
        
        for campaign in scheduled_campaigns:
            campaign.start_campaign()
            
        # Process recurring campaigns
        recurring_campaigns = SMSCampaign.objects.filter(
            is_recurring=True,
            status='completed'
        )
        
        for campaign in recurring_campaigns:
            if should_repeat_campaign(campaign, now):
                create_recurring_campaign_instance(campaign)
                
    except Exception as e:
        logger.error(f"Error processing automated campaigns: {e}")


def should_repeat_campaign(campaign: SMSCampaign, current_time: datetime) -> bool:
    """Check if recurring campaign should repeat"""
    pattern = campaign.recurrence_pattern
    if not pattern:
        return False
        
    frequency = pattern.get('frequency')  # daily, weekly, monthly
    interval = pattern.get('interval', 1)
    
    if not campaign.completed_at:
        return False
        
    if frequency == 'daily':
        return (current_time - campaign.completed_at).days >= interval
    elif frequency == 'weekly':
        return (current_time - campaign.completed_at).days >= (interval * 7)
    elif frequency == 'monthly':
        # Simplified monthly calculation
        return (current_time - campaign.completed_at).days >= (interval * 30)
        
    return False


def create_recurring_campaign_instance(original_campaign: SMSCampaign):
    """Create new instance of recurring campaign"""
    new_campaign = SMSCampaign.objects.create(
        store=original_campaign.store,
        name=f"{original_campaign.name} - {timezone.now().strftime('%Y-%m-%d')}",
        description=original_campaign.description,
        template=original_campaign.template,
        custom_message=original_campaign.custom_message,
        send_type='immediate',
        status='draft',
        is_recurring=False,  # New instance is not recurring
        created_by=original_campaign.created_by
    )
    
    # Copy segments
    new_campaign.segments.set(original_campaign.segments.all())
    new_campaign.custom_recipients = original_campaign.custom_recipients
    new_campaign.save()
    
    # Start immediately
    new_campaign.start_campaign()


# SMS Campaign Analytics
class SMSCampaignAnalytics:
    """SMS Campaign analytics and reporting"""
    
    def __init__(self, store: Store):
        self.store = store
        
    def get_campaign_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get campaign summary for specified period"""
        since_date = timezone.now() - timedelta(days=days)
        
        campaigns = SMSCampaign.objects.filter(
            store=self.store,
            created_at__gte=since_date
        )
        
        total_campaigns = campaigns.count()
        total_sent = campaigns.aggregate(
            total=models.Sum('sent_count')
        )['total'] or 0
        
        total_delivered = campaigns.aggregate(
            total=models.Sum('delivered_count')
        )['total'] or 0
        
        total_cost = campaigns.aggregate(
            total=models.Sum('actual_cost')
        )['total'] or Decimal('0')
        
        delivery_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0
        
        return {
            'total_campaigns': total_campaigns,
            'total_sent': total_sent,
            'total_delivered': total_delivered,
            'delivery_rate': round(delivery_rate, 2),
            'total_cost': float(total_cost),
            'average_cost_per_campaign': float(total_cost / total_campaigns) if total_campaigns > 0 else 0
        }
        
    def get_template_performance(self) -> List[Dict[str, Any]]:
        """Get performance metrics by template"""
        templates = SMSTemplate.objects.filter(store=self.store)
        
        performance = []
        for template in templates:
            campaigns = SMSCampaign.objects.filter(
                store=self.store,
                template=template
            )
            
            total_sent = campaigns.aggregate(
                total=models.Sum('sent_count')
            )['total'] or 0
            
            total_delivered = campaigns.aggregate(
                total=models.Sum('delivered_count')
            )['total'] or 0
            
            delivery_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0
            
            performance.append({
                'template_name': template.name,
                'template_type': template.template_type,
                'campaigns_count': campaigns.count(),
                'total_sent': total_sent,
                'total_delivered': total_delivered,
                'delivery_rate': round(delivery_rate, 2)
            })
            
        return sorted(performance, key=lambda x: x['delivery_rate'], reverse=True)
        
    def get_segment_performance(self) -> List[Dict[str, Any]]:
        """Get performance metrics by customer segment"""
        segments = CustomerSegment.objects.filter(store=self.store)
        
        performance = []
        for segment in segments:
            # Get campaigns that used this segment
            campaigns = SMSCampaign.objects.filter(
                store=self.store,
                segments=segment
            )
            
            total_recipients = 0
            total_delivered = 0
            
            for campaign in campaigns:
                reports = SMSDeliveryReport.objects.filter(
                    campaign=campaign,
                    customer__in=segment.get_customers()
                )
                total_recipients += reports.count()
                total_delivered += reports.filter(status='delivered').count()
            
            delivery_rate = (total_delivered / total_recipients * 100) if total_recipients > 0 else 0
            
            performance.append({
                'segment_name': segment.name,
                'segment_type': segment.segment_type,
                'customer_count': segment.customer_count,
                'total_recipients': total_recipients,
                'total_delivered': total_delivered,
                'delivery_rate': round(delivery_rate, 2)
            })
            
        return sorted(performance, key=lambda x: x['delivery_rate'], reverse=True)
