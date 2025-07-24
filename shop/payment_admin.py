# shop/payment_admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta

from .payment_models import (
    PaymentGateway, Payment, PaymentAttempt, 
    Refund, PaymentSettings
)


@admin.register(PaymentGateway)
class PaymentGatewayAdmin(admin.ModelAdmin):
    list_display = [
        'display_name', 'name', 'is_active', 
        'min_amount_display', 'max_amount_display', 
        'fee_display', 'created_at'
    ]
    list_filter = ['is_active', 'name', 'created_at']
    search_fields = ['display_name', 'name', 'merchant_id']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = [
        ('اطلاعات پایه', {
            'fields': ['name', 'display_name', 'is_active']
        }),
        ('تنظیمات اتصال', {
            'fields': ['merchant_id', 'api_key', 'secret_key', 'endpoint_url', 'callback_url'],
            'classes': ['collapse']
        }),
        ('محدودیت‌های مالی', {
            'fields': ['min_amount', 'max_amount', 'fixed_fee', 'percentage_fee']
        }),
        ('تنظیمات اضافی', {
            'fields': ['settings'],
            'classes': ['collapse']
        }),
        ('زمان‌بندی', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        })
    ]
    
    def min_amount_display(self, obj):
        return f"{obj.min_amount:,} ریال"
    min_amount_display.short_description = 'حداقل مبلغ'
    
    def max_amount_display(self, obj):
        return f"{obj.max_amount:,} ریال"
    max_amount_display.short_description = 'حداکثر مبلغ'
    
    def fee_display(self, obj):
        return f"{obj.fixed_fee:,} + {obj.percentage_fee}%"
    fee_display.short_description = 'کارمزد'


class PaymentAttemptInline(admin.TabularInline):
    model = PaymentAttempt
    extra = 0
    readonly_fields = ['attempt_number', 'status_code', 'message', 'created_at']
    
    def has_add_permission(self, request, obj=None):
        return False


class RefundInline(admin.TabularInline):
    model = Refund
    extra = 0
    readonly_fields = ['refund_id', 'amount_display', 'status', 'created_at']
    fields = ['refund_id', 'amount_display', 'reason', 'status', 'created_at']
    
    def amount_display(self, obj):
        return f"{obj.amount:,} ریال"
    amount_display.short_description = 'مبلغ'
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'payment_id_short', 'customer_name', 'gateway', 
        'amount_display', 'status_colored', 'created_at'
    ]
    list_filter = [
        'status', 'gateway', 'created_at', 'is_manual_verification'
    ]
    search_fields = [
        'payment_id', 'customer_name', 'customer_phone', 
        'gateway_transaction_id', 'gateway_reference_id'
    ]
    readonly_fields = [
        'payment_id', 'created_at', 'updated_at', 
        'gateway_fee_calculated', 'final_amount_calculated'
    ]
    
    fieldsets = [
        ('اطلاعات پایه', {
            'fields': [
                'payment_id', 'order', 'gateway', 'user'
            ]
        }),
        ('اطلاعات مشتری', {
            'fields': [
                'customer_name', 'customer_email', 'customer_phone'
            ]
        }),
        ('اطلاعات مالی', {
            'fields': [
                'original_amount', 'gateway_fee_calculated', 
                'final_amount_calculated', 'status'
            ]
        }),
        ('اطلاعات درگاه', {
            'fields': [
                'gateway_transaction_id', 'gateway_authority', 
                'gateway_reference_id', 'gateway_card_pan'
            ],
            'classes': ['collapse']
        }),
        ('زمان‌بندی', {
            'fields': [
                'created_at', 'updated_at', 'expires_at', 'paid_at'
            ]
        }),
        ('لاگ‌ها', {
            'fields': ['request_log', 'response_log', 'callback_log'],
            'classes': ['collapse']
        }),
        ('مدیریت', {
            'fields': [
                'description', 'failure_reason', 
                'admin_notes', 'is_manual_verification'
            ],
            'classes': ['collapse']
        })
    ]
    
    inlines = [PaymentAttemptInline, RefundInline]
    
    actions = ['mark_as_completed', 'mark_as_failed', 'export_payments']
    
    def payment_id_short(self, obj):
        return str(obj.payment_id)[:8] + '...'
    payment_id_short.short_description = 'شناسه پرداخت'
    
    def amount_display(self, obj):
        return f"{obj.final_amount:,} ریال"
    amount_display.short_description = 'مبلغ نهایی'
    
    def status_colored(self, obj):
        colors = {
            'pending': '#fbbf24',
            'processing': '#3b82f6',
            'completed': '#10b981',
            'failed': '#ef4444',
            'cancelled': '#6b7280',
            'refunded': '#8b5cf6',
            'expired': '#ef4444'
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_colored.short_description = 'وضعیت'
    
    def gateway_fee_calculated(self, obj):
        return f"{obj.gateway_fee:,} ریال"
    gateway_fee_calculated.short_description = 'کارمزد درگاه'
    
    def final_amount_calculated(self, obj):
        return f"{obj.final_amount:,} ریال"
    final_amount_calculated.short_description = 'مبلغ نهایی'
    
    def mark_as_completed(self, request, queryset):
        updated = queryset.filter(status__in=['pending', 'processing']).update(
            status='completed',
            paid_at=timezone.now(),
            is_manual_verification=True
        )
        self.message_user(request, f'{updated} پرداخت به صورت دستی تکمیل شد.')
    mark_as_completed.short_description = 'تکمیل دستی پرداخت‌های انتخاب شده'
    
    def mark_as_failed(self, request, queryset):
        updated = queryset.filter(status__in=['pending', 'processing']).update(
            status='failed',
            failure_reason='تغییر وضعیت توسط مدیر'
        )
        self.message_user(request, f'{updated} پرداخت به عنوان ناموفق علامت‌گذاری شد.')
    mark_as_failed.short_description = 'علامت‌گذاری به عنوان ناموفق'


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = [
        'refund_id_short', 'payment_customer', 'amount_display', 
        'status_colored', 'requested_by', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['refund_id', 'payment__customer_name', 'reason']
    readonly_fields = ['refund_id', 'created_at', 'processed_at']
    
    def refund_id_short(self, obj):
        return str(obj.refund_id)[:8] + '...'
    refund_id_short.short_description = 'شناسه بازگشت'
    
    def payment_customer(self, obj):
        return obj.payment.customer_name
    payment_customer.short_description = 'مشتری'
    
    def amount_display(self, obj):
        return f"{obj.amount:,} ریال"
    amount_display.short_description = 'مبلغ'
    
    def status_colored(self, obj):
        colors = {
            'pending': '#fbbf24',
            'processing': '#3b82f6',
            'completed': '#10b981',
            'failed': '#ef4444',
            'cancelled': '#6b7280'
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_colored.short_description = 'وضعیت'


@admin.register(PaymentSettings)
class PaymentSettingsAdmin(admin.ModelAdmin):
    list_display = ['id', 'payment_timeout_minutes', 'default_gateway', 'updated_at']
    
    fieldsets = [
        ('تنظیمات عمومی', {
            'fields': [
                'payment_timeout_minutes', 'retry_attempts', 'default_gateway'
            ]
        }),
        ('اعلان‌ها', {
            'fields': [
                'send_sms_notifications', 'send_email_notifications'
            ]
        }),
        ('تنظیمات مدیریتی', {
            'fields': [
                'require_admin_approval_amount', 'auto_refund_enabled'
            ]
        }),
        ('لاگ‌گیری', {
            'fields': [
                'log_all_transactions', 'log_retention_days'
            ]
        })
    ]
    
    def has_add_permission(self, request):
        return not PaymentSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False


# Register models in admin
admin.site.register(PaymentAttempt, admin.ModelAdmin)
