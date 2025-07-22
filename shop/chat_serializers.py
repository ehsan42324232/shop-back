from rest_framework import serializers
from django.contrib.auth.models import User
from .chat_models import (
    SupportAgent, ChatSession, ChatMessage, 
    ChatNotification, SupportSettings
)


class UserSerializer(serializers.ModelSerializer):
    """Basic user serializer for chat"""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name', 'email']
        
    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class SupportAgentSerializer(serializers.ModelSerializer):
    """Support agent serializer"""
    user = UserSerializer(read_only=True)
    active_chats_count = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    
    class Meta:
        model = SupportAgent
        fields = [
            'id', 'user', 'is_online', 'auto_accept_chats', 
            'max_concurrent_chats', 'active_chats_count', 
            'is_available', 'created_at'
        ]
        
    def get_active_chats_count(self, obj):
        return obj.assigned_chats.filter(status__in=['active', 'waiting']).count()
        
    def get_is_available(self, obj):
        return obj.is_online and self.get_active_chats_count(obj) < obj.max_concurrent_chats


class ChatSessionSerializer(serializers.ModelSerializer):
    """Chat session serializer"""
    customer = UserSerializer(read_only=True)
    agent = SupportAgentSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    unread_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatSession
        fields = [
            'id', 'customer', 'agent', 'subject', 'status', 'status_display',
            'priority', 'priority_display', 'customer_name', 'customer_email',
            'customer_phone', 'started_at', 'ended_at', 'updated_at',
            'customer_rating', 'customer_feedback', 'unread_count', 'last_message'
        ]
        
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
        return obj.messages.filter(is_read=False).exclude(sender=request.user).count()
        
    def get_last_message(self, obj):
        last_msg = obj.messages.order_by('-created_at').first()
        if last_msg:
            return ChatMessageSerializer(last_msg).data
        return None


class ChatMessageSerializer(serializers.ModelSerializer):
    """Chat message serializer"""
    sender = UserSerializer(read_only=True)
    message_type_display = serializers.CharField(source='get_message_type_display', read_only=True)
    file_url = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatMessage
        fields = [
            'id', 'session', 'sender', 'content', 'message_type', 
            'message_type_display', 'file_attachment', 'file_url',
            'is_read', 'created_at', 'updated_at', 'is_mine'
        ]
        
    def get_file_url(self, obj):
        if obj.file_attachment:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file_attachment.url)
            return obj.file_attachment.url
        return None
        
    def get_is_mine(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.sender == request.user
        return False


class ChatNotificationSerializer(serializers.ModelSerializer):
    """Chat notification serializer"""
    recipient = UserSerializer(read_only=True)
    session = ChatSessionSerializer(read_only=True)
    message = ChatMessageSerializer(read_only=True)
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    
    class Meta:
        model = ChatNotification
        fields = [
            'id', 'recipient', 'session', 'message', 'notification_type',
            'notification_type_display', 'title', 'body', 'is_read',
            'is_sent', 'created_at', 'sent_at'
        ]


class SupportSettingsSerializer(serializers.ModelSerializer):
    """Support settings serializer"""
    
    class Meta:
        model = SupportSettings
        fields = [
            'id', 'is_24_7', 'support_start_time', 'support_end_time',
            'welcome_message', 'offline_message', 'auto_assignment',
            'max_wait_time', 'created_at', 'updated_at'
        ]


# Create/Update serializers
class ChatSessionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating chat sessions"""
    
    class Meta:
        model = ChatSession
        fields = [
            'subject', 'priority', 'customer_name', 
            'customer_email', 'customer_phone'
        ]
        
    def validate_customer_email(self, value):
        if value:
            from django.core.validators import validate_email
            validate_email(value)
        return value


class ChatMessageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating chat messages"""
    
    class Meta:
        model = ChatMessage
        fields = ['session', 'content', 'message_type', 'file_attachment']
        
    def validate_content(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("پیام نمی‌تواند خالی باشد")
        if len(value) > 5000:
            raise serializers.ValidationError("پیام نمی‌تواند بیش از 5000 کاراکتر باشد")
        return value.strip()
        
    def validate_file_attachment(self, value):
        if value:
            # Check file size (max 10MB)
            if value.size > 10 * 1024 * 1024:
                raise serializers.ValidationError("حجم فایل نمی‌تواند بیش از 10 مگابایت باشد")
                
            # Check file type
            allowed_types = [
                'image/jpeg', 'image/png', 'image/gif', 'image/webp',
                'application/pdf', 'text/plain',
                'application/msword', 
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            ]
            if value.content_type not in allowed_types:
                raise serializers.ValidationError("نوع فایل مجاز نیست")
        return value


class SupportAgentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating support agent settings"""
    
    class Meta:
        model = SupportAgent
        fields = ['is_online', 'auto_accept_chats', 'max_concurrent_chats']
        
    def validate_max_concurrent_chats(self, value):
        if value < 1 or value > 20:
            raise serializers.ValidationError("تعداد چت همزمان باید بین 1 تا 20 باشد")
        return value


class ChatSessionRatingSerializer(serializers.ModelSerializer):
    """Serializer for rating chat sessions"""
    
    class Meta:
        model = ChatSession
        fields = ['customer_rating', 'customer_feedback']
        
    def validate_customer_rating(self, value):
        if value is not None and (value < 1 or value > 5):
            raise serializers.ValidationError("امتیاز باید بین 1 تا 5 باشد")
        return value
        
    def validate_customer_feedback(self, value):
        if value and len(value) > 1000:
            raise serializers.ValidationError("نظر نمی‌تواند بیش از 1000 کاراکتر باشد")
        return value


# Simple serializers for lists/dropdowns
class ChatSessionListSerializer(serializers.ModelSerializer):
    """Simplified chat session serializer for lists"""
    customer_name = serializers.CharField()
    agent_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    last_message_time = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatSession
        fields = [
            'id', 'customer_name', 'agent_name', 'subject', 
            'status', 'status_display', 'priority', 'started_at',
            'last_message_time', 'unread_count'
        ]
        
    def get_agent_name(self, obj):
        return obj.agent.user.get_full_name() if obj.agent else None
        
    def get_last_message_time(self, obj):
        last_msg = obj.messages.order_by('-created_at').first()
        return last_msg.created_at if last_msg else obj.started_at
        
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
        return obj.messages.filter(is_read=False).exclude(sender=request.user).count()


class SupportAgentStatsSerializer(serializers.ModelSerializer):
    """Support agent statistics serializer"""
    user = UserSerializer(read_only=True)
    total_chats = serializers.SerializerMethodField()
    active_chats = serializers.SerializerMethodField()
    avg_rating = serializers.SerializerMethodField()
    online_time_today = serializers.SerializerMethodField()
    
    class Meta:
        model = SupportAgent
        fields = [
            'id', 'user', 'is_online', 'total_chats', 'active_chats',
            'avg_rating', 'online_time_today', 'max_concurrent_chats'
        ]
        
    def get_total_chats(self, obj):
        return obj.assigned_chats.count()
        
    def get_active_chats(self, obj):
        return obj.assigned_chats.filter(status__in=['active', 'waiting']).count()
        
    def get_avg_rating(self, obj):
        from django.db.models import Avg
        avg = obj.assigned_chats.filter(
            customer_rating__isnull=False
        ).aggregate(avg_rating=Avg('customer_rating'))['avg_rating']
        return round(avg, 1) if avg else 0.0
        
    def get_online_time_today(self, obj):
        # This would require tracking online/offline times
        # For now, return a placeholder
        return "0:00" if not obj.is_online else "N/A"
