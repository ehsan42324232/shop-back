from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class SupportAgent(models.Model):
    """Support agents who handle chat"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='support_agent')
    is_online = models.BooleanField(default=False, verbose_name="آنلاین")
    last_seen = models.DateTimeField(auto_now=True, verbose_name="آخرین بازدید")
    max_concurrent_chats = models.PositiveIntegerField(default=5, verbose_name="حداکثر چت همزمان")
    
    # Agent settings
    auto_accept_chats = models.BooleanField(default=True, verbose_name="پذیرش خودکار چت")
    notification_enabled = models.BooleanField(default=True, verbose_name="اعلان‌ها فعال")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'chat_support_agent'
        verbose_name = "پشتیبان چت"
        verbose_name_plural = "پشتیبان‌های چت"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"

    @property
    def active_chats_count(self):
        return self.assigned_chats.filter(status__in=['active', 'waiting']).count()

    @property
    def is_available(self):
        return self.is_online and self.active_chats_count < self.max_concurrent_chats


class ChatSession(models.Model):
    """Live chat sessions"""
    STATUS_CHOICES = [
        ('waiting', 'در انتظار'),
        ('active', 'فعال'),
        ('closed', 'بسته شده'),
        ('transferred', 'انتقال داده شده'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions', verbose_name="مشتری")
    agent = models.ForeignKey(SupportAgent, on_delete=models.SET_NULL, null=True, blank=True, 
                            related_name='assigned_chats', verbose_name="پشتیبان")
    
    # Session details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting', verbose_name="وضعیت")
    subject = models.CharField(max_length=255, blank=True, verbose_name="موضوع")
    priority = models.CharField(max_length=10, choices=[
        ('low', 'کم'),
        ('normal', 'عادی'),
        ('high', 'بالا'),
        ('urgent', 'فوری')
    ], default='normal', verbose_name="اولویت")
    
    # Customer info
    customer_name = models.CharField(max_length=255, blank=True, verbose_name="نام مشتری")
    customer_email = models.EmailField(blank=True, verbose_name="ایمیل مشتری")
    customer_phone = models.CharField(max_length=20, blank=True, verbose_name="تلفن مشتری")
    
    # Session metadata
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="شروع چت")
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name="پایان چت")
    customer_rating = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="امتیاز مشتری")
    customer_feedback = models.TextField(blank=True, verbose_name="نظر مشتری")
    
    # Tracking
    customer_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP مشتری")
    user_agent = models.TextField(blank=True, verbose_name="User Agent")
    referrer_url = models.URLField(blank=True, verbose_name="URL ارجاع")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'chat_session'
        verbose_name = "جلسه چت"
        verbose_name_plural = "جلسات چت"
        indexes = [
            models.Index(fields=['customer']),
            models.Index(fields=['agent']),
            models.Index(fields=['status']),
            models.Index(fields=['started_at']),
        ]

    def __str__(self):
        return f"چت {self.customer_name or self.customer.username} - {self.get_status_display()}"

    @property
    def duration(self):
        if self.ended_at:
            return self.ended_at - self.started_at
        return timezone.now() - self.started_at

    def close_session(self):
        self.status = 'closed'
        self.ended_at = timezone.now()
        self.save()


class ChatMessage(models.Model):
    """Chat messages"""
    MESSAGE_TYPES = [
        ('text', 'متن'),
        ('image', 'تصویر'),
        ('file', 'فایل'),
        ('system', 'سیستم'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages', verbose_name="جلسه")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="فرستنده")
    
    # Message content
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text', verbose_name="نوع پیام")
    content = models.TextField(verbose_name="محتوا")
    file_attachment = models.FileField(upload_to='chat_files/', null=True, blank=True, verbose_name="پیوست")
    
    # Message status
    is_read = models.BooleanField(default=False, verbose_name="خوانده شده")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان خواندن")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ارسال")

    class Meta:
        db_table = 'chat_message'
        verbose_name = "پیام چت"
        verbose_name_plural = "پیام‌های چت"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['sender']),
            models.Index(fields=['is_read']),
        ]

    def __str__(self):
        return f"پیام از {self.sender.username} در {self.created_at}"

    def mark_as_read(self, user=None):
        if not self.is_read and (not user or user != self.sender):
            self.is_read = True
            self.read_at = timezone.now()
            self.save()


class ChatNotification(models.Model):
    """Push notifications for chat"""
    NOTIFICATION_TYPES = [
        ('new_message', 'پیام جدید'),
        ('chat_assigned', 'چت واگذار شده'),
        ('chat_closed', 'چت بسته شده'),
        ('customer_joined', 'مشتری وارد شد'),
        ('agent_offline', 'پشتیبان آفلاین شد'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_notifications', verbose_name="گیرنده")
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, null=True, blank=True, verbose_name="جلسه")
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, null=True, blank=True, verbose_name="پیام")
    
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, verbose_name="نوع اعلان")
    title = models.CharField(max_length=255, verbose_name="عنوان")
    body = models.TextField(verbose_name="متن اعلان")
    
    # Notification status
    is_sent = models.BooleanField(default=False, verbose_name="ارسال شده")
    is_read = models.BooleanField(default=False, verbose_name="خوانده شده")
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان ارسال")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان خواندن")
    
    # Push notification data
    push_token = models.TextField(blank=True, verbose_name="توکن پوش")
    response_data = models.JSONField(default=dict, verbose_name="پاسخ سرویس پوش")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'chat_notification'
        verbose_name = "اعلان چت"
        verbose_name_plural = "اعلان‌های چت"
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"اعلان {self.title} برای {self.recipient.username}"


class SupportSettings(models.Model):
    """Global support settings"""
    # Operating hours
    monday_start = models.TimeField(default='09:00', verbose_name="شروع دوشنبه")
    monday_end = models.TimeField(default='18:00', verbose_name="پایان دوشنبه")
    tuesday_start = models.TimeField(default='09:00', verbose_name="شروع سه‌شنبه")
    tuesday_end = models.TimeField(default='18:00', verbose_name="پایان سه‌شنبه")
    wednesday_start = models.TimeField(default='09:00', verbose_name="شروع چهارشنبه")
    wednesday_end = models.TimeField(default='18:00', verbose_name="پایان چهارشنبه")
    thursday_start = models.TimeField(default='09:00', verbose_name="شروع پنج‌شنبه")
    thursday_end = models.TimeField(default='18:00', verbose_name="پایان پنج‌شنبه")
    friday_start = models.TimeField(default='09:00', verbose_name="شروع جمعه")
    friday_end = models.TimeField(default='18:00', verbose_name="پایان جمعه")
    saturday_start = models.TimeField(default='09:00', verbose_name="شروع شنبه")
    saturday_end = models.TimeField(default='18:00', verbose_name="پایان شنبه")
    sunday_start = models.TimeField(default='09:00', verbose_name="شروع یکشنبه")
    sunday_end = models.TimeField(default='18:00', verbose_name="پایان یکشنبه")
    
    # Chat settings
    is_24_7 = models.BooleanField(default=True, verbose_name="پشتیبانی 24/7")
    auto_offline_minutes = models.PositiveIntegerField(default=5, verbose_name="دقایق آفلاین خودکار")
    max_wait_time_minutes = models.PositiveIntegerField(default=10, verbose_name="حداکثر زمان انتظار")
    
    # Messages
    welcome_message = models.TextField(default="سلام! چطور می‌توانیم کمکتان کنیم؟", verbose_name="پیام خوش‌آمدگویی")
    offline_message = models.TextField(default="متأسفانه در حال حاضر پشتیبان آنلاین نداریم. لطفاً پیام خود را بگذارید.", verbose_name="پیام آفلاین")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'chat_support_settings'
        verbose_name = "تنظیمات پشتیبانی"
        verbose_name_plural = "تنظیمات پشتیبانی"

    def __str__(self):
        return "تنظیمات پشتیبانی"

    @classmethod
    def get_settings(cls):
        """Get or create support settings"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings

    def is_support_online(self):
        """Check if support is currently online"""
        if self.is_24_7:
            return True
        
        # Check if any agent is online
        return SupportAgent.objects.filter(is_online=True).exists()
