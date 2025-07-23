from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .homepage_models import ContactRequest, PlatformSettings, Newsletter, FAQ


@admin.register(ContactRequest)
class ContactRequestAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'phone', 'business_type_display', 'status',
        'created_at_formatted', 'assigned_to', 'follow_up_date'
    ]
    list_filter = [
        'status', 'business_type', 'created_at', 
        'assigned_to', 'follow_up_date'
    ]
    search_fields = ['name', 'phone', 'email', 'company_name']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'ip_address', 
        'user_agent', 'source', 'utm_source', 'utm_medium', 'utm_campaign'
    ]
    
    fieldsets = [
        ('اطلاعات تماس', {
            'fields': ('name', 'phone', 'email')
        }),
        ('اطلاعات کسب‌وکار', {
            'fields': ('business_type', 'company_name', 'website_url', 'estimated_products')
        }),
        ('پیام و درخواست', {
            'fields': ('message',)
        }),
        ('مدیریت درخواست', {
            'fields': ('status', 'assigned_to', 'follow_up_date', 'notes')
        }),
        ('اطلاعات سیستم', {
            'fields': ('id', 'created_at', 'updated_at', 'source', 'ip_address'),
            'classes': ('collapse',)
        }),
        ('اطلاعات بازاریابی', {
            'fields': ('utm_source', 'utm_medium', 'utm_campaign', 'user_agent'),
            'classes': ('collapse',)
        })
    ]
    
    actions = ['mark_as_contacted', 'mark_as_follow_up', 'assign_to_me']
    
    def business_type_display(self, obj):
        return obj.get_business_type_display()
    business_type_display.short_description = 'نوع کسب‌وکار'
    
    def created_at_formatted(self, obj):
        return obj.created_at.strftime('%Y/%m/%d %H:%M')
    created_at_formatted.short_description = 'تاریخ ایجاد'
    
    def mark_as_contacted(self, request, queryset):
        updated = queryset.update(status='contacted')
        self.message_user(request, f'{updated} درخواست به عنوان "تماس گرفته شده" علامت‌گذاری شد.')
    mark_as_contacted.short_description = 'علامت‌گذاری به عنوان تماس گرفته شده'
    
    def mark_as_follow_up(self, request, queryset):
        updated = queryset.update(
            status='follow_up',
            follow_up_date=timezone.now() + timezone.timedelta(days=3)
        )
        self.message_user(request, f'{updated} درخواست برای پیگیری تنظیم شد.')
    mark_as_follow_up.short_description = 'تنظیم برای پیگیری'
    
    def assign_to_me(self, request, queryset):
        updated = queryset.update(assigned_to=request.user)
        self.message_user(request, f'{updated} درخواست به شما تخصیص داده شد.')
    assign_to_me.short_description = 'تخصیص به من'


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    fieldsets = [
        ('محتوای صفحه اصلی', {
            'fields': ('hero_title', 'hero_subtitle')
        }),
        ('آمار پلتفرم', {
            'fields': (
                'active_stores_count', 'daily_sales_amount',
                'customer_satisfaction', 'years_experience'
            )
        }),
        ('اطلاعات تماس', {
            'fields': ('support_email', 'support_phone')
        }),
        ('شبکه‌های اجتماعی', {
            'fields': ('telegram_url', 'instagram_url', 'twitter_url', 'linkedin_url')
        }),
        ('تنظیمات SEO', {
            'fields': ('meta_title', 'meta_description')
        }),
        ('تنظیمات عملکرد', {
            'fields': (
                'maintenance_mode', 'maintenance_message',
                'enable_registration', 'enable_demo_requests', 'enable_chat_support'
            )
        })
    ]
    
    def has_add_permission(self, request):
        # Only allow one instance
        return not PlatformSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion
        return False


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = ['email', 'is_active', 'source', 'created_at']
    list_filter = ['is_active', 'source', 'created_at']
    search_fields = ['email']
    readonly_fields = ['created_at', 'updated_at', 'ip_address']
    
    actions = ['activate_subscriptions', 'deactivate_subscriptions']
    
    def activate_subscriptions(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} اشتراک فعال شد.')
    activate_subscriptions.short_description = 'فعال کردن اشتراک‌ها'
    
    def deactivate_subscriptions(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} اشتراک غیرفعال شد.')
    deactivate_subscriptions.short_description = 'غیرفعال کردن اشتراک‌ها'


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ['question_preview', 'category', 'is_active', 'sort_order']
    list_filter = ['category', 'is_active']
    search_fields = ['question', 'answer']
    list_editable = ['is_active', 'sort_order']
    
    fieldsets = [
        (None, {
            'fields': ('question', 'answer', 'category')
        }),
        ('تنظیمات نمایش', {
            'fields': ('is_active', 'sort_order')
        })
    ]
    
    def question_preview(self, obj):
        return obj.question[:80] + '...' if len(obj.question) > 80 else obj.question
    question_preview.short_description = 'سوال'


# Add custom admin site header
admin.site.site_header = 'پنل مدیریت پلتفرم مال'
admin.site.site_title = 'مال Admin'
admin.site.index_title = 'مدیریت پلتفرم'
