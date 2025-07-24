# shop/realtime_chat_models.py
"""
Mall Platform - Real-time Chat Models
Complete chat system for customer support
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

class ChatRoom(models.Model):
    """Chat room between customer and store"""
    ROOM_STATUS = [
        ('active', 'فعال'),
        ('closed', 'بسته شده'),
        ('waiting', 'در انتظار'),
        ('archived', 'بایگانی شده')
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey('Store', on_delete=models.CASCADE, related_name='chat_rooms')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customer_chats')
    agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_chats')
    
    status = models.CharField(max_length=20, choices=ROOM_STATUS, default='waiting')
    subject = models.CharField(max_length=200, verbose_name='موضوع')
    priority = models.CharField(max_length=20, choices=[
        ('low', 'کم'),
        ('medium', 'متوسط'), 
        ('high', 'زیاد'),
        ('urgent', 'فوری')
    ], default='medium')
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    # Metrics
    response_time = models.IntegerField(default=0, help_text='Average response time in seconds')
    customer_satisfaction = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    
    class Meta:
        verbose_name = 'اتاق گفتگو'
        verbose_name_plural = 'اتاق‌های گفتگو'
        ordering = ['-updated_at']
        db_table = 'realtime_chat_room'
    
    def __str__(self):
        return f"{self.store.name} - {self.customer.get_full_name()}"
    
    def get_unread_count(self, user):
        """Get unread message count for user"""
        return self.messages.filter(
            is_read=False,
            sender__ne=user
        ).count()


class RealtimeChatMessage(models.Model):
    """Individual realtime chat message - renamed to avoid conflict"""
    MESSAGE_TYPES = [
        ('text', 'متن'),
        ('image', 'تصویر'),
        ('file', 'فایل'),
        ('system', 'سیستم'),
        ('product', 'محصول')
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField(verbose_name='محتوا')
    
    # File attachments
    attachment = models.FileField(upload_to='chat_files/', null=True, blank=True)
    attachment_name = models.CharField(max_length=255, blank=True)
    
    # Product reference
    product = models.ForeignKey('ProductInstance', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'پیام گفتگوی لحظه‌ای'
        verbose_name_plural = 'پیام‌های گفتگوی لحظه‌ای'
        ordering = ['created_at']
        db_table = 'realtime_chat_message'
    
    def __str__(self):
        return f"{self.sender.get_full_name()}: {self.content[:50]}"
    
    def mark_as_read(self, user):
        """Mark message as read by user"""
        if self.sender != user and not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()


class ChatAgent(models.Model):
    """Chat support agent profile"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='chat_agent')
    store = models.ForeignKey('Store', on_delete=models.CASCADE, related_name='chat_agents')
    
    is_online = models.BooleanField(default=False)
    max_concurrent_chats = models.IntegerField(default=5)
    current_chat_count = models.IntegerField(default=0)
    
    # Skills and departments
    departments = models.JSONField(default=list, help_text='Departments this agent handles')
    languages = models.JSONField(default=list, help_text='Languages agent speaks')
    
    # Performance metrics
    total_chats = models.IntegerField(default=0)
    avg_response_time = models.IntegerField(default=0)
    customer_rating = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'مشاور گفتگو'
        verbose_name_plural = 'مشاوران گفتگو'
        db_table = 'realtime_chat_agent'
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.store.name}"
    
    def can_accept_chat(self):
        """Check if agent can accept new chat"""
        return self.is_online and self.current_chat_count < self.max_concurrent_chats


class RealtimeChatSession(models.Model):
    """Realtime chat session tracking - renamed to avoid conflicts"""
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='sessions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Session data
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'جلسه گفتگوی لحظه‌ای'
        verbose_name_plural = 'جلسات گفتگوی لحظه‌ای'
        db_table = 'realtime_chat_session'


class RealtimeChatNotification(models.Model):
    """Realtime chat notifications - renamed to avoid conflicts"""
    NOTIFICATION_TYPES = [
        ('new_message', 'پیام جدید'),
        ('agent_assigned', 'اختصاص مشاور'),
        ('chat_closed', 'بستن گفتگو'),
        ('customer_waiting', 'انتظار مشتری')
    ]
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='realtime_chat_notifications')
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='realtime_notifications')
    
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    is_read = models.BooleanField(default=False)
    is_sent = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'اعلان گفتگوی لحظه‌ای'
        verbose_name_plural = 'اعلانات گفتگوی لحظه‌ای'
        ordering = ['-created_at']
        db_table = 'realtime_chat_notification'


class ChatTemplate(models.Model):
    """Quick response templates"""
    store = models.ForeignKey('Store', on_delete=models.CASCADE, related_name='chat_templates')
    name = models.CharField(max_length=100, verbose_name='نام قالب')
    content = models.TextField(verbose_name='محتوا')
    category = models.CharField(max_length=50, verbose_name='دسته‌بندی')
    
    is_active = models.BooleanField(default=True)
    usage_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'قالب پاسخ سریع'
        verbose_name_plural = 'قالب‌های پاسخ سریع'
        db_table = 'chat_template'
    
    def __str__(self):
        return self.name


class ChatSettings(models.Model):
    """Chat system settings per store"""
    store = models.OneToOneField('Store', on_delete=models.CASCADE, related_name='chat_settings')
    
    # Availability
    is_enabled = models.BooleanField(default=True)
    working_hours_start = models.TimeField(default='09:00')
    working_hours_end = models.TimeField(default='18:00')
    working_days = models.JSONField(default=list, help_text='List of working days (0=Monday)')
    
    # Auto responses
    welcome_message = models.TextField(default='سلام! چطور می‌تونم کمکتون کنم؟')
    offline_message = models.TextField(default='متاسفانه در حال حاضر آنلاین نیستیم. لطفا پیام بذارید.')
    
    # Behavior
    auto_assign_agent = models.BooleanField(default=True)
    require_email = models.BooleanField(default=False)
    allow_file_upload = models.BooleanField(default=True)
    max_file_size = models.IntegerField(default=5, help_text='Max file size in MB')
    
    # Notifications
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'تنظیمات گفتگو'
        verbose_name_plural = 'تنظیمات گفتگو'
        db_table = 'chat_settings'
