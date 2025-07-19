from django.db import models
from django.contrib.auth.models import User
from django.core.validators import URLValidator
from django.utils.text import slugify
import uuid
import json
from .models import Store, Product, TimestampedModel


class SocialPlatform(TimestampedModel):
    """Social media platforms configuration"""
    PLATFORM_CHOICES = [
        ('instagram', 'Instagram'),
        ('telegram', 'Telegram'),
        ('twitter', 'Twitter'),
        ('facebook', 'Facebook'),
        ('tiktok', 'TikTok'),
        ('youtube', 'YouTube'),
    ]
    
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='social_platforms', verbose_name="فروشگاه")
    platform_type = models.CharField(max_length=20, choices=PLATFORM_CHOICES, verbose_name="نوع پلتفرم")
    username = models.CharField(max_length=100, verbose_name="نام کاربری")
    api_credentials = models.JSONField(default=dict, blank=True, verbose_name="اعتبارات API")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    last_sync = models.DateTimeField(null=True, blank=True, verbose_name="آخرین همگام‌سازی")
    
    class Meta:
        db_table = 'shop_social_platform'
        verbose_name = "پلتفرم اجتماعی"
        verbose_name_plural = "پلتفرم‌های اجتماعی"
        unique_together = ['store', 'platform_type', 'username']
        
    def __str__(self):
        return f"{self.store.name} - {self.get_platform_type_display()}: {self.username}"


class Story(TimestampedModel):
    """Social media stories"""
    CONTENT_TYPES = [
        ('image', 'تصویر'),
        ('video', 'ویدیو'),
        ('text', 'متن'),
        ('mixed', 'ترکیبی'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    platform = models.ForeignKey(SocialPlatform, on_delete=models.CASCADE, related_name='stories', verbose_name="پلتفرم")
    external_id = models.CharField(max_length=255, verbose_name="شناسه خارجی")
    content_type = models.CharField(max_length=10, choices=CONTENT_TYPES, verbose_name="نوع محتوا")
    
    # Content data
    text_content = models.TextField(blank=True, verbose_name="محتوای متنی")
    media_urls = models.JSONField(default=list, verbose_name="لینک‌های رسانه")
    thumbnail_url = models.URLField(blank=True, verbose_name="لینک تصویر کوچک")
    
    # Metadata
    view_count = models.PositiveIntegerField(default=0, verbose_name="تعداد بازدید")
    like_count = models.PositiveIntegerField(default=0, verbose_name="تعداد لایک")
    comment_count = models.PositiveIntegerField(default=0, verbose_name="تعداد کامنت")
    share_count = models.PositiveIntegerField(default=0, verbose_name="تعداد اشتراک")
    
    # Story specific
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ انقضا")
    is_highlighted = models.BooleanField(default=False, verbose_name="هایلایت شده")
    
    # Processing status
    is_processed = models.BooleanField(default=False, verbose_name="پردازش شده")
    processing_error = models.TextField(blank=True, verbose_name="خطای پردازش")
    
    # Extracted content for easy selection
    extracted_images = models.JSONField(default=list, verbose_name="تصاویر استخراج شده")
    extracted_videos = models.JSONField(default=list, verbose_name="ویدیوهای استخراج شده")
    extracted_text = models.TextField(blank=True, verbose_name="متن استخراج شده")
    
    class Meta:
        db_table = 'shop_story'
        verbose_name = "استوری"
        verbose_name_plural = "استوری‌ها"
        unique_together = ['platform', 'external_id']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['platform', 'created_at']),
            models.Index(fields=['content_type']),
            models.Index(fields=['is_processed']),
        ]
        
    def __str__(self):
        return f"Story {self.external_id} - {self.platform.platform_type}"


class Post(TimestampedModel):
    """Social media posts"""
    CONTENT_TYPES = [
        ('image', 'تصویر'),
        ('video', 'ویدیو'),
        ('text', 'متن'),
        ('carousel', 'کاروسل'),
        ('mixed', 'ترکیبی'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    platform = models.ForeignKey(SocialPlatform, on_delete=models.CASCADE, related_name='posts', verbose_name="پلتفرم")
    external_id = models.CharField(max_length=255, verbose_name="شناسه خارجی")
    content_type = models.CharField(max_length=10, choices=CONTENT_TYPES, verbose_name="نوع محتوا")
    
    # Content data
    caption = models.TextField(blank=True, verbose_name="کپشن")
    hashtags = models.JSONField(default=list, verbose_name="هشتگ‌ها")
    mentions = models.JSONField(default=list, verbose_name="منشن‌ها")
    media_urls = models.JSONField(default=list, verbose_name="لینک‌های رسانه")
    thumbnail_url = models.URLField(blank=True, verbose_name="لینک تصویر کوچک")
    
    # Post URL
    post_url = models.URLField(blank=True, verbose_name="لینک پست")
    
    # Engagement metrics
    like_count = models.PositiveIntegerField(default=0, verbose_name="تعداد لایک")
    comment_count = models.PositiveIntegerField(default=0, verbose_name="تعداد کامنت")
    share_count = models.PositiveIntegerField(default=0, verbose_name="تعداد اشتراک")
    save_count = models.PositiveIntegerField(default=0, verbose_name="تعداد ذخیره")
    
    # Post metadata
    published_at = models.DateTimeField(verbose_name="تاریخ انتشار")
    location = models.CharField(max_length=255, blank=True, verbose_name="موقعیت")
    
    # Processing status
    is_processed = models.BooleanField(default=False, verbose_name="پردازش شده")
    processing_error = models.TextField(blank=True, verbose_name="خطای پردازش")
    
    # Extracted content for easy selection
    extracted_images = models.JSONField(default=list, verbose_name="تصاویر استخراج شده")
    extracted_videos = models.JSONField(default=list, verbose_name="ویدیوهای استخراج شده")
    extracted_text = models.TextField(blank=True, verbose_name="متن استخراج شده")
    
    class Meta:
        db_table = 'shop_post'
        verbose_name = "پست"
        verbose_name_plural = "پست‌ها"
        unique_together = ['platform', 'external_id']
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['platform', 'published_at']),
            models.Index(fields=['content_type']),
            models.Index(fields=['is_processed']),
        ]
        
    def __str__(self):
        return f"Post {self.external_id} - {self.platform.platform_type}"


class ContentSelection(TimestampedModel):
    """Track which content has been selected for products"""
    CONTENT_TYPE_CHOICES = [
        ('story', 'استوری'),
        ('post', 'پست'),
    ]
    
    MEDIA_TYPE_CHOICES = [
        ('image', 'تصویر'),
        ('video', 'ویدیو'),
        ('text', 'متن'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='content_selections', verbose_name="محصول")
    content_type = models.CharField(max_length=10, choices=CONTENT_TYPE_CHOICES, verbose_name="نوع محتوا")
    content_id = models.UUIDField(verbose_name="شناسه محتوا")  # References Story.id or Post.id
    
    # Selected media details
    selected_media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, verbose_name="نوع رسانه انتخاب شده")
    selected_media_urls = models.JSONField(default=list, verbose_name="لینک‌های رسانه انتخاب شده")
    selected_text = models.TextField(blank=True, verbose_name="متن انتخاب شده")
    
    # Usage settings
    use_as_product_image = models.BooleanField(default=False, verbose_name="استفاده به عنوان تصویر محصول")
    use_in_description = models.BooleanField(default=False, verbose_name="استفاده در توضیحات")
    use_as_gallery = models.BooleanField(default=False, verbose_name="استفاده در گالری")
    
    # Metadata
    selection_notes = models.TextField(blank=True, verbose_name="یادداشت انتخاب")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    
    class Meta:
        db_table = 'shop_content_selection'
        verbose_name = "انتخاب محتوا"
        verbose_name_plural = "انتخاب‌های محتوا"
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['content_type', 'content_id']),
        ]
        
    def __str__(self):
        return f"{self.product.title} - {self.get_content_type_display()}"
    
    @property
    def source_content(self):
        """Get the source content object (Story or Post)"""
        if self.content_type == 'story':
            try:
                return Story.objects.get(id=self.content_id)
            except Story.DoesNotExist:
                return None
        elif self.content_type == 'post':
            try:
                return Post.objects.get(id=self.content_id)
            except Post.DoesNotExist:
                return None
        return None


class ContentSyncLog(TimestampedModel):
    """Log content synchronization operations"""
    SYNC_STATUS_CHOICES = [
        ('started', 'شروع شده'),
        ('processing', 'در حال پردازش'),
        ('completed', 'تکمیل شده'),
        ('failed', 'ناموفق'),
        ('partial', 'موفقیت جزئی'),
    ]
    
    platform = models.ForeignKey(SocialPlatform, on_delete=models.CASCADE, related_name='sync_logs', verbose_name="پلتفرم")
    sync_type = models.CharField(max_length=20, choices=[('stories', 'استوری‌ها'), ('posts', 'پست‌ها')], verbose_name="نوع همگام‌سازی")
    status = models.CharField(max_length=20, choices=SYNC_STATUS_CHOICES, default='started', verbose_name="وضعیت")
    
    # Statistics
    total_items_found = models.PositiveIntegerField(default=0, verbose_name="کل آیتم‌های یافت شده")
    new_items_created = models.PositiveIntegerField(default=0, verbose_name="آیتم‌های جدید ایجاد شده")
    items_updated = models.PositiveIntegerField(default=0, verbose_name="آیتم‌های به‌روزرسانی شده")
    items_failed = models.PositiveIntegerField(default=0, verbose_name="آیتم‌های ناموفق")
    
    # Error details
    error_details = models.JSONField(default=list, verbose_name="جزئیات خطا")
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="شروع شده در")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="تکمیل شده در")
    
    class Meta:
        db_table = 'shop_content_sync_log'
        verbose_name = "لاگ همگام‌سازی محتوا"
        verbose_name_plural = "لاگ‌های همگام‌سازی محتوا"
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['platform', 'started_at']),
            models.Index(fields=['status']),
        ]
        
    def __str__(self):
        return f"{self.platform} - {self.get_sync_type_display()} - {self.status}"
